import re

import jellyfish
from tqdm import tqdm

from test4vul.parsing import count_params, get_invocations


def get_substrings_method_name(method_name: str):
    words = []
    for part in method_name.split('_'):
        words.extend(re.findall(
            r'[A-Z]+(?=[A-Z][a-z])|'  # acronyms before normal words (URIParser)
            r'[A-Z]?[a-z]+|'          # normal camelCase words
            r'[A-Z]+|'                # standalone acronyms
            r'\d+',                   # numbers (optional)
            part
        ))
    substrings: list[str] = []
    n = len(words)
    for i in range(n):
        for j in range(i + 1, n + 1):
            substrings.append(''.join(words[i:j]))
    return substrings


def measure_focal_relevance(prod_method_signature: str, prod_class_fqn: str, test_class_package: str, test_class_name: str, test_method_name: str, test_method_name_substrings: list[str], invocations_in_test: list):
    test_keywords = ["test", "Test", "tests", "Tests", "testCase", "testcase", "TestCase"]
    scores = {}

    prod_method_name = prod_method_signature.split("(", 1)[0]
    prod_class_package, prod_class_name = prod_class_fqn.rsplit(".", 1) if "." in prod_class_fqn else ("", prod_class_fqn)
    scores["packageMatch"] = int(test_class_package == prod_class_package)

    clean_test_class_name = test_class_name
    for to_remove in test_keywords:
        clean_test_class_name = clean_test_class_name.removeprefix(to_remove).removesuffix(to_remove)
    scores["classNameMatch"] = int(clean_test_class_name == prod_class_name)

    clean_test_method_name = test_method_name
    for to_remove in test_keywords:
        clean_test_method_name = clean_test_method_name.removeprefix(to_remove).removesuffix(to_remove)
    scores["methodNameMatchCase"] = int(clean_test_method_name == prod_method_name)
    scores["methodNameMatch"] = int(clean_test_method_name.lower() == prod_method_name.lower())

    scores["methodNameContainCase"] = int(prod_method_name in test_method_name_substrings)
    lower_test_method_name_substrings = [a.lower() for a in test_method_name_substrings]
    scores["methodNameContain"] = int(prod_method_name.lower() in lower_test_method_name_substrings)

    best_substring = max(lower_test_method_name_substrings, key=lambda x: jellyfish.jaro_similarity(x, prod_method_name.lower()))
    scores["methodNameSimil"] = jellyfish.jaro_similarity(best_substring, prod_method_name.lower())

    invocation_matches = []
    for inv in invocations_in_test:
        param_count = count_params(prod_method_signature)
        if "..." in prod_method_signature:
            arg_match = inv["args"] >= param_count - 1
        else:
            arg_match = inv["args"] == param_count
        matches = {
            "invocationNameMatch": int(inv["name"] == prod_method_name),
            "invocationArgsMatch": int(arg_match),
            "invocationTypeMatch": int(inv["type"] == prod_class_name)
        }
        invocation_matches.append(matches)
    best_match = max(invocation_matches, key=lambda x: int("".join(map(str, x.values())), 2))
    scores.update(best_match)

    # TODO Other options to consider if needed
    # - Record if, after ignoring invocations to getters, setters and assertions, only the invocation to the production method remains (VERY unlikely, so not really important)
    # - If the production method is a constructor (its name is the same as the class name), then record if test method name has "create" or "construct" and there is a contruction invocation
    # - The test case may call a public method that is actually an entry point for the real target method. Like in the SolrQueryExecutor case in CVE-2023-48241. Currently, the matching we're doing produces a FN and a FP.

    # print(f'- Production method "{prod_method_signature}"')
    # print(f'  - Test class package match with its class package "{prod_class_package}": {scores["packageMatch"]}')
    # print(f'  - Test class match with its class name "{prod_class_name}": {scores["classNameMatch"]}')
    # print(f'  - Test method name fitting (case sensitive) its name "{prod_method_name}": {scores["methodNameMatchCase"]}')
    # print(f'  - Test method name fitting (case insensitive) its name "{prod_method_name}": {scores["methodNameMatch"]}')
    # print(f'  - Test method name contains (case sensitive) its name "{prod_method_name}": {scores["methodNameContainCase"]}')
    # print(f'  - Test method name contains (case insensitive) its name "{prod_method_name}": {scores["methodNameContain"]}')
    # print(f'  - Invocation found with the same name: {scores["invocationNameMatch"]}')
    # print(f'  - Invocation found with the same nr. arguments: {scores["invocationArgsMatch"]}')
    # print(f'  - Caller of the invocation has the right class "{prod_class_name}": {scores["invocationTypeMatch"]}')
    return scores


def is_focal_method_for_test(prod_method_signature: str, prod_class_fqn: str, test_class_package: str, test_class_name: str, test_method_name: str, test_method_name_substrings: list[str], invocations_in_test: list):
    scores = measure_focal_relevance(prod_method_signature, prod_class_fqn, test_class_package, test_class_name, test_method_name, test_method_name_substrings, invocations_in_test)
    # if scores["methodNameContain"] == 1:
    # if scores["invocationNameMatch"] == 1 and scores["invocationArgsMatch"] == 1:
    # if scores["classNameMatch"] == 1 or scores["methodNameContain"] == 1 or (scores["invocationNameMatch"] == 1 and scores["invocationArgsMatch"] == 1 and scores["invocationTypeMatch"] == 1):
    return scores["classNameMatch"] == 1 and (scores["methodNameContain"] == 1 or (scores["invocationNameMatch"] == 1 and scores["invocationArgsMatch"] == 1 and scores["invocationTypeMatch"] == 1))


def filter_non_focal_methods(tests: list[dict]):
    # Test specific substrings: {"test", "tests", "testcase", "given", "when", "then", "should", "expect"}
    tests_with_focal_methods = []
    for a_test in tqdm(tests, desc="Mapping focal methods to tests"):
        test_entry = {k: v for k, v in a_test.items()
                      if k not in {"test_file", "test_class_node", "test_method_node", "vuln_methods_metadata", "fixed_methods_metadata", "pairs_metadata"}
                      }
        test_class_fqn: str = a_test["test_class"]
        test_class_package, test_class_name = test_class_fqn.rsplit(".", 1) if "." in test_class_fqn else ("", test_class_fqn)
        test_method_signature: str = a_test["test_method"]
        test_method_name = test_method_signature.split("(", 1)[0]
        test_method_name_substrings = get_substrings_method_name(test_method_name)
        invocations_in_test = get_invocations(a_test["test_method_node"], a_test["test_class_node"])
        if "vuln_methods" in a_test and "fixed_methods" in a_test:
            test_entry["vuln_methods"] = []
            test_entry["fixed_methods"] = []
            for code, metadata in zip(a_test["vuln_methods"], a_test["vuln_methods_metadata"]):
                if is_focal_method_for_test(metadata["method"], metadata["class"], test_class_package, test_class_name, test_method_name, test_method_name_substrings, invocations_in_test):
                    test_entry["vuln_methods"].append(code)
            for code, metadata in zip(a_test["fixed_methods"], a_test["fixed_methods_metadata"]):
                if is_focal_method_for_test(metadata["method"], metadata["class"], test_class_package, test_class_name, test_method_name, test_method_name_substrings, invocations_in_test):
                    test_entry["fixed_methods"].append(code)
            # print(f"Resulting vuln methods: {len(test_method_entry['vuln_methods'])}")
            # print(f"Resulting fixed methods: {len(test_method_entry['fixed_methods'])}")
            if len(test_entry["vuln_methods"]) > 0 or len(test_entry["fixed_methods"]) > 0:
                tests_with_focal_methods.append(test_entry)
        elif "pairs" in a_test:
            test_entry["pairs"] = []
            for codes, metadatas in zip(a_test["pairs"], a_test["pairs_metadata"]):
                vuln_is_focal = is_focal_method_for_test(
                    metadatas["vuln_method"]["method"], metadatas["vuln_method"]["class"],
                    test_class_package, test_class_name, test_method_name, test_method_name_substrings, invocations_in_test)
                fixed_is_focal = is_focal_method_for_test(
                    metadatas["fixed_method"]["method"], metadatas["fixed_method"]["class"],
                    test_class_package, test_class_name, test_method_name, test_method_name_substrings, invocations_in_test)
                if vuln_is_focal and fixed_is_focal:
                    test_entry["pairs"].append({"vuln_method": codes["vuln_method"], "fixed_method": codes["fixed_method"]})
            if len(test_entry["pairs"]) > 0:
                tests_with_focal_methods.append(test_entry)
    return tests_with_focal_methods
