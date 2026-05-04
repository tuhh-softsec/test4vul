from typing import Optional

from tree_sitter import Language, Parser, Node
import tree_sitter_java as tsjava

JAVA_LANGUAGE = Language(tsjava.language())


def _make_parser() -> Parser:
    return Parser(JAVA_LANGUAGE)


def _parse(source_code: str) -> Node:
    """Parse Java source and returns the root_node of the syntax tree"""
    tree = _make_parser().parse(source_code.encode("utf-8"))
    return tree.root_node


def _direct_children_of_type(node: Node, *type_names: str) -> list[Node]:
    """Return direct children whose type is in *type_names*."""
    return [c for c in node.children if c.type in type_names]


def _all_descendants_of_type(node: Node, *type_names: str) -> list[Node]:
    """Depth-first search for all descendant nodes of the given type(s)."""
    results = []
    for child in node.children:
        if child.type in type_names:
            results.append(child)
        results.extend(_all_descendants_of_type(child, *type_names))
    return results


def _get_node_name(node: Node) -> str:
    if node is None:
        return ""
    name_node = node.child_by_field_name("name")
    return name_node.text.decode("utf-8") if name_node is not None else ""


def retrieve_methods_of_top_class_from_source(
    source_code: str,
    full_info: bool = True,
    show_errors: bool = True,
) -> list[tuple]:
    """
    Parse *source_code* and return a list of
    (root_node, class_node, method_node, method_text, start_line, end_line)
    tuples for every method in every top-level class.
    """
    methods = []
    try:
        root = _parse(source_code)
    except Exception:
        if show_errors:
            print("- Error during parsing")
        return []
    if root.has_error:
        if show_errors:
            print("- Error during parsing")
        return []
    for class_node in _direct_children_of_type(root, "class_declaration"):
        # Method declarations are found inside class bodies
        class_body = class_node.child_by_field_name("body")
        if class_body is None:
            continue
        for method_node in _direct_children_of_type(class_body, "method_declaration"):
            if full_info:
                method_text = method_node.text.decode("utf-8")
                if method_text == "":
                    continue
                start = method_node.start_point[0] + 1
                end = method_node.end_point[0] + 1
                method_text = method_text.replace("\n\t", "\n").strip()
            else:
                method_text, start, end = None, None, None
            methods.append((root, class_node, method_node, method_text, start, end))
    return list(dict.fromkeys(methods))


def get_class_fqn(class_node: Node) -> str:
    """Return the fully-qualified class name, e.g. 'com.example.MyClass'."""
    prefix = ""
    root = class_node
    while root.parent is not None:
        root = root.parent
    for package in _direct_children_of_type(root, "package_declaration"):
        for p_name in _direct_children_of_type(package, "scoped_identifier", "identifier"):
            prefix += p_name.text.decode()
            break
    return f"{prefix}.{_get_node_name(class_node)}"


def get_method_name(method_node: Node) -> str:
    return _get_node_name(method_node)


def get_method_signature(method_node: Node) -> str:
    """Return a signature string like 'myMethod(int x, String y)'."""
    params_node = method_node.child_by_field_name("parameters")
    params: list[str] = []
    if params_node:
        for param in _direct_children_of_type(params_node, "formal_parameter", "spread_parameter"):
            is_varargs = param.type == "spread_parameter"

            annotations = [
                "@" + _get_node_name(ann)
                for ann in _direct_children_of_type(param, "marker_annotation", "annotation")
            ]

            modifiers = [
                c.text.decode()
                for c in param.children
                if c.type == "modifier" or c.text.decode() == "final"
            ]

            # Types include array dims, e.g. 'int[]', and varargs three dots
            if is_varargs:
                gen_type_nodes = _direct_children_of_type(param, "generic_type")
                if len(gen_type_nodes) > 0:
                    type_node = gen_type_nodes[0]
                else:
                    type_node = [c for c in param.children if "type" in c.type][0]
                param_ident = _get_node_name(_direct_children_of_type(param, "variable_declarator")[0])
            else:
                type_node = param.child_by_field_name("type")
                param_ident = _get_node_name(param)
            type_name = (type_node.text.decode() if type_node else "") + ("..." if is_varargs else "")

            ann_str = " ".join(annotations) + " " if annotations else ""
            mod_str = " ".join(modifiers) + " " if modifiers else ""
            params.append(f"{ann_str}{mod_str}{type_name} {param_ident}")
    return _get_node_name(method_node) + "(" + ", ".join(params) + ")"


def retrieve_class_method_nodes_from_source(
    source_code: str,
    class_fqn: str,
    method_signature_or_name: str,
    exact_method_signature_match: bool = True,
) -> tuple[Optional[Node], Optional[Node]]:
    """
    Find and return (class_node, method_node) for the given class FQN + method signature.
    Returns (class_node, None) when the class is found but the method is not,
    and (None, None) when the class itself cannot be found.
    """
    try:
        root = _parse(source_code)
    except Exception:
        return None, None

    for class_node in _direct_children_of_type(root, "class_declaration"):
        if get_class_fqn(class_node) != class_fqn:
            continue
        class_body = class_node.child_by_field_name("body")
        if class_body is None:
            return class_node, None
        for method_node in _direct_children_of_type(class_body, "method_declaration"):
            sig = get_method_signature(method_node)
            if exact_method_signature_match:
                if sig == method_signature_or_name:
                    return class_node, method_node
            else:
                if sig.split("(", 1)[0] == method_signature_or_name:
                    return class_node, method_node
        # class found, method not found
        return class_node, None
    return None, None


def resolve_identifier_type(
    name: str,
    class_node: Node,
    method_node: Node,
) -> Optional[str]:
    """
    Resolve *name* (an identifier) to its declared type by searching (in order):
      1. Local variable declarations in the method body
      2. Method parameters
      3. Class fields
    """
    if name is None:
        return None

    # 1. Local variable declarations
    for local_var_decl in _all_descendants_of_type(method_node, "local_variable_declaration"):
        type_node = local_var_decl.child_by_field_name("type")
        if type_node:
            for declarator in _all_descendants_of_type(local_var_decl, "variable_declarator"):
                if _get_node_name(declarator) == name:
                    return type_node.text.decode()

    # 2. Method parameters
    params_node = method_node.child_by_field_name("parameters")
    if params_node:
        for param in _direct_children_of_type(params_node, "formal_parameter"):
            if _get_node_name(param) == name:
                type_node = param.child_by_field_name("type")
                return type_node.text.decode()

    # 3. Class fields
    class_body = class_node.child_by_field_name("body")
    if class_body:
        for field_decl in _direct_children_of_type(class_body, "field_declaration"):
            type_node = field_decl.child_by_field_name("type")
            if type_node:
                for declarator in _all_descendants_of_type(field_decl, "variable_declarator"):
                    if _get_node_name(declarator) == name:
                        return type_node.text.decode()

    return None


def get_invocations(
    method_node: Node,
    class_node: Node
) -> list[dict]:
    """
    Return a list of dicts describing every method invocation inside *method_node*:
      {"name": str, "args": int, "type": str | None}
    """
    invocations = []
    for invocation_node in _all_descendants_of_type(method_node, "method_invocation"):
        # Method name
        invoked_method_name = _get_node_name(invocation_node)

        # Argument count
        args_node = invocation_node.child_by_field_name("arguments")
        nr_args = len(args_node.named_children) if args_node else 0

        # Caller / qualifier (the object the method is called on)
        obj_node = invocation_node.child_by_field_name("object")
        caller_identifier = obj_node.text.decode() if obj_node else ""

        # Resolve identifier to a type (only works for simple identifiers)
        caller_type_name = resolve_identifier_type(caller_identifier, class_node, method_node)

        invocations.append({
            "name": invoked_method_name,
            "args": nr_args,
            "type": caller_type_name,
        })
    return invocations
