import json
from importlib import resources

TEST4VUL_DATASET_NAME = "test4vul.json"
TEST4VUL_FOCAL_DATASET_NAME = "test4vul_focal.json"


def load_test4vul() -> list[dict]:
    with resources.files(f"{__package__}.res").joinpath(TEST4VUL_DATASET_NAME).open("r") as f:
        return json.load(f)
