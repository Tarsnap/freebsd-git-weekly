import os.path
import re
import typing

# We normally don't allow "from", but in this case it's worth it.
from typing import Any

import commits_periodical.utils

VALID_ACTS_ON = {"filenames", "summary", "message"}
VALID_RE_FUNC = {"search", "match"}


class Classifier:
    def __init__(self, orig: dict) -> None:
        self.metadata = {k: v for k, v in orig.items() if k.startswith("_")}
        self.rules = {k: v for k, v in orig.items() if not k.startswith("_")}

    def get_metadata(self, key: str, default: Any = None) -> Any:
        return self.metadata.get(key, default)

    def items(self) -> typing.ItemsView[str, Any]:
        return self.rules.items()


def sanity_check(categories: dict, orig_classifiers: dict) -> None:
    cats = categories.keys()

    # We must have a "Meta" section, even if it's empty
    if "Meta" not in orig_classifiers:
        raise KeyError('There must be a "Meta" section')

    # Sanity check for non-categories
    for section in orig_classifiers.values():
        for key in section:
            # Skip underscores
            if key.startswith("_"):
                continue

            # Check that all classifier-categories are in categories
            if key not in cats:
                raise ValueError(f"Not a category: {key}")

    # Sanity check for _acts_on
    for name, section in orig_classifiers.items():
        if name == "Meta":
            continue
        acts_on = section.get("_acts_on")
        if not acts_on:
            raise ValueError(f'{name}: missing "_acts_on"')
        if acts_on not in VALID_ACTS_ON:
            raise ValueError(
                f'{name}: "_acts_on" must be one of {VALID_ACTS_ON}'
            )

    # Sanity check for _re_func
    for name, section in orig_classifiers.items():
        if name == "Meta":
            continue
        re_func = section.get("_re_func")
        if not re_func:
            # re_func is optional
            continue
        if re_func not in VALID_RE_FUNC:
            raise ValueError(
                f'{name}: "_re_func" must be one of {VALID_RE_FUNC}'
            )

    # Sanity check for regexes
    for name, section in orig_classifiers.items():
        for key, value in section.items():
            # At the moment, any list in this file contains potential regexes.
            # If that changes in the future, this check will need to be changed.
            if isinstance(value, list):
                for pattern in value:
                    try:
                        re.compile(pattern)
                    except re.error as e:
                        msg = f"{name} {key}: bad regex: {pattern!r} {e}"
                        raise ValueError(msg)

    # Sanity check for alphabetical order
    for section in orig_classifiers.values():
        for key, value in section.items():
            if not isinstance(value, list):
                continue

            # Check order
            if value != sorted(value):
                raise ValueError(f"Not in alphabetical order: {value}")


class ProjectData:
    def __init__(self, project_dirname: str) -> None:
        self.dirname = os.path.expanduser(project_dirname)
        self._load()

    def _load(self) -> None:
        self.categories = commits_periodical.utils.read_toml(
            os.path.join(self.dirname, "categories.toml")
        )
        self.orig_classifiers = commits_periodical.utils.read_toml(
            os.path.join(self.dirname, "classify.toml")
        )

        sanity_check(self.categories, self.orig_classifiers)

        self.classifiers = {}
        for section in sorted(self.orig_classifiers.keys()):
            if section == "Meta":
                self.meta = self.orig_classifiers["Meta"]
                continue

            # Create a Classifier for each section.
            classifier = self.orig_classifiers[section]
            self.classifiers[section] = Classifier(classifier)
