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
        for method_node in _get_method_declarations(class_node):
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


def _walk_to_root(node: Node) -> Node:
    root = node
    while root.parent is not None:
        root = root.parent
    return root


def get_class_fqn(class_node: Node) -> str:
    """Return the fully-qualified class name, e.g. 'com.example.MyClass'."""
    prefix = ""
    root = _walk_to_root(class_node)
    for package in _direct_children_of_type(root, "package_declaration"):
        for p_name in _direct_children_of_type(package, "scoped_identifier", "identifier"):
            prefix += p_name.text.decode()
            break
    return f"{prefix}.{_get_node_name(class_node)}"


def get_method_name(method_node: Node) -> str:
    return _get_node_name(method_node)


def get_class_name(class_node: Node) -> str:
    return _get_node_name(class_node)


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


def _get_method_declarations(class_node: Node) -> list[Node]:
    # Method declarations are found inside class bodies
    class_body = class_node.child_by_field_name("body")
    if class_body is None:
        return []
    return [mn for mn in _direct_children_of_type(class_body, "method_declaration")]


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
        method_declarations = _get_method_declarations(class_node)
        if len(method_declarations) == 0:
            return class_node, None
        for method_node in method_declarations:
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


def resolve_identifier_simple_type(
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


def _build_static_import_map(class_node: Node) -> tuple[dict[str, str], list[str]]:
    """
    Collect all static imports in a class node.

    Returns
    -------
    explicit_map : dict[str, str]
        member name -> Fully qualified class name
        e.g. `import static java.util.Collections.sort` -> {"sort": "java.util.Collections"}
    wildcard_classes : list[str]
        Fully qualified class names brought in via `import static foo.Bar.*`
    """
    explicit_map: dict[str, str] = {}
    wildcard_classes: list[str] = []
    root = _walk_to_root(class_node)
    for imp_decl_node in _direct_children_of_type(root, "import_declaration"):
        # tree-sitter represents `static` as an unnamed keyword child
        is_static = any(
            (not child.is_named) and child.text == b"static"
            for child in imp_decl_node.children
        )
        if not is_static:
            continue
        # Pull the dotted path out of the raw text, e.g. "import static java.util.Collections.sort;" -> ["java", "util", "Collections", "sort"]
        raw = imp_decl_node.text.decode()
        path_str = (
            raw.replace("import", "", 1)
               .replace("static", "", 1)
               .replace(";", "")
               .strip()
        )
        class_fqn, member = path_str.rsplit(".", 1)
        class_fqn = class_fqn.strip()
        member = member.strip()  # It can be a method name, a field name, or wildcard "*"
        if member == "*":
            if class_fqn:
                wildcard_classes.append(class_fqn)
        else:
            explicit_map[member] = class_fqn
    return explicit_map, wildcard_classes


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

        if caller_identifier:
            # Resolve the identifier to a SIMPLE type inside the same class
            caller_type_name = resolve_identifier_simple_type(caller_identifier, class_node, method_node)
            # If the resolution did not suceeded, it is likely that the caller is a class (i.e., the method is static). So, we use the identifier as the type
            if caller_type_name is None:
                caller_type_name = caller_identifier
        else:
            # We start by searching the method internally (same class)
            for method_node in _get_method_declarations(class_node):
                if get_method_name(method_node) == invoked_method_name:
                    caller_type_name = get_class_name(class_node)
            
            # If still not found, we search among the static imports
            if caller_type_name is None:
                static_imports_map, static_imports_wildcards = _build_static_import_map(class_node)
                caller_type_name = static_imports_map.get(invoked_method_name)
                if caller_type_name is not None and "." in caller_type_name:
                    caller_type_name = caller_type_name.rsplit(".", 1)[1]
                # TODO If not found, should parse all the classes in `static_imports_wildcards` and check if they have a method with name `caller_identifier`. To do so, we need to look into all other classes, so we need to have access to all files. Not urgent for now.
            

        invocations.append({
            "name": invoked_method_name,
            "args": nr_args,
            "type": caller_type_name,
        })
    return invocations
