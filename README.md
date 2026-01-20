# Test4Vul

This repository contains the dataset **Test4Vul**, containing validated real-world JUnit test methods that are security-related (i.e., they witness a vulnerability). In particular, some of them have also been confirmed to be related to specific CVEs.

The main file is `test4vul.json`, which currently has 259 entries. Each entry is manually-confirmed vulnerability-witnessing test.

Please, see the [MSR'26 paper](https://arxiv.org/abs/2502.03365) for more details about its inner workings.

If you are looking for MSR'26 version of Test4Vul, please see the [Zenodo package](https://doi.org/10.5281/zenodo.18258566).

If you are looking for the tool that originated Test4Vul, i.e., **VuTeCo**, please see https://github.com/tuhh-softsec/vuteco.

# Data Structure

Each has the following data fields:
- `repo`: the name of the repository;
- `revision`: the commit hash;
- `file_path`: the path to the JUnit class file inside the repository containing the test method;
- `class_name`: the fully-qualified name of the belonging class;
- `method_name`: the test method name;
- `code`: the raw source code
- `matched_vulns`: the list of matches CVEs, if any.

# Key Statistics

|||
|--|--|
| Test Methods with 1 matched CVEs | 27 |
| Test Methods with 2+ matched CVEs | 8 |
| Test Methods with no matched CVEs | 224 |
| **Total Test Methods** | **259** |

# Future Work

This repository is under improvement. These are some activities that will be done to improve the reusability of the dataset and the clarify of this REAMDE:

- Download the class files
- Related the test methods to the right production class/method
- Provide the Docker images to run such tests
