import json
import os
from argparse import ArgumentParser

from tqdm import tqdm

from test4vul.focal import get_substrings_method_name, is_focal_method_for_test
from test4vul.mining import (blob_to_text, get_commit_from_repo_url,
                             get_java_production_files_as_blobs)
from test4vul.parsing import (get_class_fqn, get_invocations, retrieve_class_method_nodes_from_source,
                              get_method_name, get_method_signature, retrieve_methods_of_top_class_from_source)
from test4vul.resources import TEST4VUL_DATASET_NAME, load_test4vul


def retrieve_production_methods(prod_files: list) -> list[dict]:
    production_methods = []
    for a_prod_file_blob in tqdm(prod_files):
        prod_methods_in_file = retrieve_methods_of_top_class_from_source(blob_to_text(a_prod_file_blob), show_errors=False)  # full_info=False,)
        for _, class_node, method_node, method_text, start, end in prod_methods_in_file:
            p_method = {
                "file_path": a_prod_file_blob.path,
                "class_name": get_class_fqn(class_node),
                "method_name": get_method_name(method_node),
                "method_signature": get_method_signature(method_node),
                "code": method_text,
                "startline": start,
                "endline": end,
            }
            production_methods.append(p_method)
    return production_methods


def retrieve_metadata_for_test(a_test_file_content: str, a_test_class_name: str, a_test_method_name: str):
    metadata = {}
    metadata["test_class_node"], metadata["test_method_node"] = retrieve_class_method_nodes_from_source(
        a_test_file_content, a_test_class_name, a_test_method_name, exact_method_signature_match=False)
    if metadata["test_class_node"] is None or metadata["test_method_node"] is None:
        input("This should not happen!")
        return metadata
    metadata["test_substrings"] = get_substrings_method_name(a_test_method_name)
    metadata["test_invocations"] = get_invocations(metadata["test_method_node"], metadata["test_class_node"])
    return metadata


def main():
    argparser = ArgumentParser()
    argparser.add_argument("--debug", action="store_true", help="Enable DEBUG run")
    argparser.add_argument(
        "--out-dir", type=str, default=os.curdir, help="Where to export the output. By default it is the current working directory."
    )
    args = argparser.parse_args()

    test4vul = load_test4vul()
    print(f"Analyzing a total of {len(test4vul)} tests")
    last_p_url = None
    last_p_rev = None
    last_rev_commit = None
    last_production_methods = None
    for test in test4vul:
        p_url = f'https://github.com/{test["repo"]}'
        p_rev = test["revision"]
        print(f'\nTest "{test["class_name"]}::{test["method_name"]}" in project {p_url} at revision {p_rev}')
        if last_p_url == p_url and last_p_rev == p_rev:
            rev_commit = last_rev_commit
            production_methods = last_production_methods
        else:
            rev_commit = get_commit_from_repo_url(p_url, p_rev)
            if rev_commit is None:
                continue
            java_prod_file_blobs = get_java_production_files_as_blobs(rev_commit, extension="java")
            print(f"Retrieving metadata of production methods in project {p_url} at revision {p_rev}")
            if args.debug:
                print("##### DEBUG: READING ONLY A SUBSET OF PRODUCTION FILES #####")
                production_methods = retrieve_production_methods(java_prod_file_blobs[:100])
            else:
                production_methods = retrieve_production_methods(java_prod_file_blobs)

        print(f'Retrieving metadata for the test from file "{test["file_path"]}"')
        test["metadata"] = {
            "test_file_content": None,
            "test_class_node": None,
            "test_method_node": None,
            "test_substrings": None,
            "test_invocations": None,
        }
        test["focal_methods"] = []
        for obj in rev_commit._c_object.tree.traverse():
            if test["metadata"]["test_file_content"] is not None:
                break
            if getattr(obj, "type") != 'blob':  # 'blob' = file, 'tree' = directory
                continue
            if test["file_path"] == os.fspath(getattr(obj, "path")):
                test["metadata"]["test_file_content"] = blob_to_text(obj)
        if test["metadata"]["test_file_content"] is None:
            print(f'- FAILED TO READ the source')
            continue
        print(f'- SUCCESSFULLY found the source!')
        test["metadata"].update(retrieve_metadata_for_test(test["metadata"]["test_file_content"], test["class_name"], test["method_name"]))
        if test["metadata"]["test_class_node"] is None or test["metadata"]["test_method_node"] is None:
            print(f"- FAILED TO BUILD NODES from source for {test['test_method']} in {test['test_file']}")
            continue

        print(f'Searching the focal methods across {len(production_methods)}')
        test_class_package, test_class_name = test["class_name"].rsplit(".", 1) if "." in test["class_name"] else ("", test["class_name"])
        test_method_name = test["method_name"]
        for prod_meth in production_methods:
            if is_focal_method_for_test(prod_meth["method_signature"], prod_meth["class_name"], test_class_package, test_class_name, test_method_name, test["metadata"]["test_substrings"], test["metadata"]["test_invocations"]):
                test["focal_methods"].append(prod_meth)
                print(f'- Linked production method {prod_meth["class_name"]}::{prod_meth["method_signature"]}')
        if len(test["focal_methods"]) == 0:
            print(f'- No focal method found :(')
        del test["metadata"]
        os.makedirs(args.out_dir, exist_ok=True)
        outfile = os.path.join(args.out_dir, TEST4VUL_DATASET_NAME)
        with open(outfile, "w") as fout:
            json.dump(test4vul, fout, indent=2)
        print(f"File {outfile} updated")

        last_p_url = p_url
        last_p_rev = p_rev
        last_rev_commit = rev_commit
        last_production_methods = production_methods

    print(f'Linked a total of {len([fm for test in test4vul for fm in test["focal_methods"]])} focal methods')


if __name__ == "__main__":
    main()
