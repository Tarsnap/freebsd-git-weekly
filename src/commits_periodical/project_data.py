import os.path

import commits_periodical.utils


class Classifier:
    def __init__(self, orig: dict):
        self.metadata = {k: v for k, v in orig.items() if k.startswith("_")}
        self.rules = {k: v for k, v in orig.items() if not k.startswith("_")}

    def get_metadata(self, key, default=None):
        return self.metadata.get(key, default)

    def items(self):
        return self.rules.items()


def sanity_check(categories: dict, orig_classifiers: dict):
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
