# Test4Vul

This repository contains the dataset **Test4Vul**, containing validated real-world JUnit test methods that are security-related (i.e., they witness a vulnerability). In particular, some of them have also been confirmed to be related to specific CVEs.

The main file is `test4vul/test4vul/res/test4vul.json`, which currently has 259 entries. Each entry is manually-confirmed vulnerability-witnessing test.

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
| Test Methods with 1 matched CVEs | 27 |
| Test Methods with 2+ matched CVEs | 8 |
| Test Methods with no matched CVEs | 224 |
| **Total Test Methods** | **259** |

# Future Work

This repository is under improvement. These are some activities that will be done to improve the reusability of the dataset and the clarify of this REAMDE:

- Download the class files
- Provide the Docker images to run such tests

# Link to Focal Methods

The link to the focal methods of each test has been made with a custom script (called `test4vul`) in the `test4vul/` directory.

These are the base requirements to re-run it:

- Python 3.13
- A **stable Internet connection** (e.g., for downloading the Python packages and cloning remote repositories).

This script has been tested on a Linux-based OS so far.

**NOTE**: The following commands assumes that `python` is the default alias for the selected Python installation. You can change to `python3` without issues.

## Installation

Test4Vul can be installed from source locally. Clone this repository and move into the `test4vul/` directory:

```sh
cd test4vul/
```

If this is the first use of this tool, create the virtual environment and activate it.

```sh
python -m venv ./venv
source venv/bin/activate
```

Install the required dependencies in the virtual environment (can take some seconds), as listed in `pyproject.toml`:

```sh
python -m pip install -e .
```

## Running Test4Vul

After installing it, Test4Vul can be run with the command `test4vul`, which is equivalent to `python -m test4vul.cli` (you can choose any). This command is usable as long as the virtual environment remains active.

```sh
test4vul --out-dir <OUTPUT-DIRECTORY>
```

If `--out-dir` is not specified, the ouput directory will be the current working directory.
