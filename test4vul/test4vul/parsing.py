from typing import Optional

import javalang as jl


def get_method_text_and_pos(method_node: jl.ast.Node, source_text: str):
    source_tokens = list(jl.tokenizer.tokenize(source_text))
    brace_count = 0
    started = False
    last_tok = None
    for tok in source_tokens:
        if tok.position.line < method_node.position.line:
            continue
        if isinstance(tok, jl.tokenizer.Separator) and tok.value == '{':
            brace_count += 1
            if not started:
                started = True
        if isinstance(tok, jl.tokenizer.Separator) and tok.value == '}':
            brace_count -= 1
            if started and brace_count == 0:
                last_tok = tok
                break
    if last_tok is None:
        return "", 0, 0
    start_pos = method_node.position.line
    end_pos = last_tok.position.line
    method_text = "\n".join(source_text.splitlines()[start_pos - 1: end_pos])
    return method_text, start_pos, end_pos


def retrieve_methods_from_class_source(source_code: str, full_info: bool = True, show_errors: bool = True) -> list:
    methods = []
    try:
        cu = jl.parse.parse(source_code)
    except:
        if show_errors:
            print("- Error during parsing")
        return []
    # types contain only the top level classes
    for class_node in list(cu.types):
        if not isinstance(class_node, jl.parser.tree.ClassDeclaration):
            continue
        # for _, method_node in list(class_node.filter(jl.parser.tree.MethodDeclaration)):
        #    if method_node in class_node.methods:
        for method_node in class_node.methods:
            if full_info:
                method_text, start, end = get_method_text_and_pos(method_node, source_code)
                if method_text == "":
                    continue
                method_text = method_text.replace("\n\t", "\n").strip()
            else:
                method_text, start, end = None, None, None
            methods.append((cu, class_node, method_node, method_text, start, end))
    return list(dict.fromkeys(methods))


def get_class_fqn(cu, class_node):
    prefix = f"{cu.package.name}." if cu.package else ""
    return f"{prefix}{class_node.name}"


def get_method_signature(method_node: jl.parser.tree.MethodDeclaration) -> str:
    params = []
    for p in method_node.parameters:
        annotations = " ".join(['@' + ann.name for ann in p.annotations]) + " " if p.annotations else ""
        modifiers = " ".join(p.modifiers) + " " if p.modifiers else ""
        dimensions = '[]' * len(p.type.dimensions)
        params.append(f"{annotations}{modifiers}{p.type.name}{dimensions} {p.name}")
    return method_node.name + "(" + ", ".join(params) + ")"


def find_identifier_type(name: str, class_node: jl.parser.tree.ClassDeclaration, method_node: jl.parser.tree.MethodDeclaration):
    if name is None:
        return None
    caller_type_name = None
    for _, var_decl_node in method_node.filter(jl.parser.tree.LocalVariableDeclaration):
        for decl in getattr(var_decl_node, "declarators"):
            if decl.name == name:
                caller_type_name = getattr(getattr(var_decl_node, "type"), "name")
        if not caller_type_name:
            for p in getattr(method_node, "parameters"):
                if p.name == name:
                    caller_type_name = getattr(getattr(var_decl_node, "type"), "name")
    if not caller_type_name:
        for field in class_node.fields:
            for decl in getattr(field, "declarators"):
                if decl.name == name:
                    caller_type_name = getattr(getattr(field, "type"), "name")
    return caller_type_name


def get_class_method_nodes_from_class_source(class_source_text: str, class_fqn: str, method_signature_or_name: str, exact_method_signature_match: bool = True) -> tuple[Optional[jl.parser.tree.ClassDeclaration], Optional[jl.parser.tree.MethodDeclaration]]:
    try:
        cu = jl.parse.parse(class_source_text)
    except:
        return None, None
    # types contain only the top level classes
    for class_node in list(cu.types):
        if not isinstance(class_node, jl.parser.tree.ClassDeclaration):
            continue
        if get_class_fqn(cu, class_node) == class_fqn:
            for method_node in class_node.methods:
                # print(get_method_signature(method_node), "vs", method_name)
                if exact_method_signature_match:
                    if get_method_signature(method_node) == method_signature_or_name:
                        return class_node, method_node
                elif get_method_signature(method_node).split("(", 1)[0] == method_signature_or_name:
                    return class_node, method_node
            return class_node, None
    return None, None


def get_invocations(method_node: jl.parser.tree.MethodDeclaration, class_node: jl.parser.tree.ClassDeclaration) -> list[dict]:
    invocations = []
    for _, invocation_node in method_node.filter(jl.parser.tree.MethodInvocation):
        # invocation_str = process_invocation_node(invocation_node)
        invoked_method_name = getattr(invocation_node, "member")
        nr_args = len(getattr(invocation_node, "arguments"))
        caller_identifier = getattr(invocation_node, "qualifier")  # Can be an empty string
        caller_type_name = find_identifier_type(caller_identifier, class_node, method_node)
        invocation = {
            "name": invoked_method_name,
            "args": nr_args,
            "type": caller_type_name
        }
        invocations.append(invocation)
    return invocations
