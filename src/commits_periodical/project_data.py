import os.path

import commits_periodical.utils


def _invert_dict(orig: dict):
    inverted = {}
    for key, value in orig.items():
        for item in value:
            # Quick sanity check
            assert item not in inverted

            inverted[item] = key
    return inverted


def sanity_check(orig_classifiers):
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

        sanity_check(self.orig_classifiers)

        self.classifiers = {}
        for section in sorted(self.orig_classifiers.keys()):
            if section == "Meta":
                self.meta = self.orig_classifiers["Meta"]
                continue

            # Invert the contents of each section, other than the "acts_on" key.
            classifier = self.orig_classifiers[section]
            acts_on = classifier.pop("acts_on")
            self.classifiers[section] = _invert_dict(classifier)
            self.classifiers[section]["acts_on"] = acts_on
