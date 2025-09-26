import os.path

import commits_periodical.utils


def _invert_dict(orig: dict):
    inverted = {}
    for key, value in orig.items():
        # Don't invert underscore keys
        if key.startswith("_"):
            inverted[key] = value
            continue

        for item in value:
            # Quick sanity check
            assert item not in inverted

            inverted[item] = key
    return inverted


def sanity_check(categories, orig_classifiers):
    cats = categories.keys()

    # Sanity check for non-categories
    for name, section in orig_classifiers.items():
        for key in section:
            # Skip underscores
            if key.startswith("_"):
                continue

            # Check that all classifier-categories are in categories
            if key not in cats:
                raise ValueError(f"Not a category: {key}")

    # Sanity check for alphabetical order
    for name, section in orig_classifiers.items():
        for key, value in section.items():
            if not isinstance(value, list):
                continue

            # Check order
            if value != sorted(value):
                raise ValueError(f"Not in alphabetical order: {value}")


class ProjectData:
    def __init__(self, project_dirname: str):
        self.dirname = os.path.expanduser(project_dirname)
        self._load()

    def _load(self):
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

            # Invert the contents of each section, other than those beginning
            # with an underscore.
            classifier = self.orig_classifiers[section]
            self.classifiers[section] = _invert_dict(classifier)
