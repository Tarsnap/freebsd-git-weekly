import collections
import os.path

import tomlkit


def in_progress(metadata: dict):
    if "in_progress" in metadata:
        return metadata["in_progress"]
    return False


class MetadataFile:
    def __init__(self, project_dirname):
        self.project_dirname = project_dirname
        self.filename = os.path.join(project_dirname, "metadata.toml")
        with open(self.filename, encoding="utf8") as fp:
            self.doc = tomlkit.load(fp)

        self.latest_datestr = max(self.doc.keys())

    def get_latest_filename(self):
        latest_filename = os.path.join(
            self.project_dirname, f"{self.latest_datestr}.toml"
        )
        return latest_filename

    def get_latest_datestr(self):
        return self.latest_datestr

    def get_metadata(self, datestr):
        return self.doc[datestr]

    def get_start_dates(self):
        return self.doc.keys()

    def save(self):
        out = tomlkit.dumps(self.doc)
        with open(self.filename, "w", encoding="utf8") as fp:
            fp.write(out)


class WeekEntry:
    """An entry in the week's summaries; may be a single commit or a group of
    commits.
    """

    def __init__(self, ref):
        self.ref = ref

    @property
    def name(self):
        """Name of this entry.  If it's a single commit, the name is the
        githash; if it's a group, the name is a unique string.
        """
        return self.ref[0]

    @property
    def githash(self):
        return self.ref[0]

    @property
    def cat(self):
        """Category of this entry."""
        if "mc" in self.ref[1]:
            return self.ref[1]["mc"]
        if "ac" in self.ref[1]:
            return self.ref[1]["ac"]
        return "unknown"

    @property
    def manual_cat(self):
        return self.ref[1]["mc"]

    @property
    def automatic_cat(self):
        """Category of this entry."""
        if "ac" in self.ref[1]:
            return self.ref[1]["ac"]
        return "unknown"

    def has_auto_cat(self):
        return "ac" in self.ref[1]

    def set_keyword_cat(self, newcat):
        """Set the category of this commit."""
        self.ref[1]["kc"] = newcat

    def set_revert_cat(self, newcat):
        """Set the category of this commit."""
        self.ref[1]["rc"] = newcat

    def set_group(self, group):
        self.ref[1]["g"] = group

    def has_group(self):
        return "g" in self.ref[1]

    def groupname(self):
        return self.ref[1]["g"]

    def is_cat_disputed(self):
        if "mc" not in self.ref[1]:
            return False
        if self.automatic_cat != self.manual_cat:
            return True
        return False

    def remove_emphasized(self):
        del self.ref[1]["ae"]

    def set_emphasized(self):
        self.ref[1]["ae"] = 1

    def set_auto_cat(self, cat, section, pattern):
        self.ref[1]["ac"] = cat
        self.ref[1]["ac_section"] = section
        self.ref[1]["ac_pattern"] = pattern

    def is_style(self):
        if "ms" in self.ref[1] and self.ref[1]["ms"] == 1:
            return True
        if "as" in self.ref[1] and self.ref[1]["as"] == 1:
            return True
        return False

    def is_revert(self):
        if "ac" in self.ref[1] and self.ref[1]["ac"] == "reverts":
            return True
        return False

    def is_emphasized(self):
        """Is this entry emphasized?"""
        # If there's a manual judgement, that takes priority
        if "me" in self.ref[1]:
            if self.ref[1]["me"] == 1:
                return True
            return False

        if "ae" in self.ref[1] and self.ref[1]["ae"] == 1:
            return True
        return False

    def clear_automatic_annotation(self):
        for key in [
            "ac",
            "ac_pattern",
            "ac_section",
            "ae",
            "g",
        ]:
            if key in self.ref[1]:
                del self.ref[1][key]


class Week:
    """A document which details all commits within a range."""

    def __init__(self, filename):
        self.filename = filename
        self._load()

    def _load(self):
        try:
            with open(self.filename, encoding="utf8") as fp:
                self.doc = tomlkit.load(fp)
        except FileNotFoundError:
            # Start a new file
            self.doc = tomlkit.document()

        self.entries = {item[0]: WeekEntry(item) for item in self.doc.items()}
        self.groups = collections.defaultdict(list)
        for entry in self.entries.values():
            if entry.has_group():
                self.groups[entry.groupname()].append(entry)

    def save(self):
        """Save the document to disk."""
        out = tomlkit.dumps(self.doc)
        with open(self.filename, "w", encoding="utf8") as fp:
            fp.write(out)

    def get_entries(self):
        """Generator to return each commit."""
        yield from self.entries.items()

    def get_hashes(self):
        """Get all hashes."""
        yield from self.entries

    def get_entry(self, githash):
        return self.entries[githash]

    def _get_groupname(self, basename):
        """Get a name to distinguish a new group of commits."""
        groupnum = 0
        while True:
            groupname = f"{basename}-{groupnum:02d}"
            if groupname not in self.groups:
                break
            groupnum += 1

            # Panic if we've looped too much
            assert groupnum < 99

        return groupname

    def set_revert_cat(self, githash, newcat):
        self.entries[githash].set_revert_cat(newcat)

    def set_keyword_cat(self, githash, newcat):
        self.entries[githash].set_keyword_cat(newcat)

    def set_group(self, githashes, basename, groupname=None):
        if not groupname:
            groupname = self._get_groupname(basename)
        self.groups[groupname] = githashes

        for githash in githashes:
            self.entries[githash].set_group(groupname)

    def add_commit(self, githash):
        """Add a commit."""
        commit = tomlkit.table()
        self.doc[githash] = commit
        self.entries[githash] = WeekEntry((githash, commit))

    def clear_automatic_annotations(self):
        for githash in self.get_hashes():
            self.entries[githash].clear_automatic_annotation()
        self.groups.clear()
