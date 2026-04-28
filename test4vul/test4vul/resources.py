import json
from importlib import resources

TEST4VUL_DATASET_NAME = "test4vul.json"


def load_test4vul() -> dict:
    with resources.files(f"{__package__}.res").joinpath(TEST4VUL_DATASET_NAME).open("r") as f:
        return json.load(f)
