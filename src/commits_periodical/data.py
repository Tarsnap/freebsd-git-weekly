import collections
import os.path

import tomlkit


class Report:
    """This is metadata about a single report.  With the exception of
    set_end_including(), it is read-only.
    """

    def __init__(self, table: tomlkit.items.Table):
        self.table = table

    def __contains__(self, key):
        return key in self.table

    def __getitem__(self, key):
        return self.table[key]

    def get_display_name(self):
        if "display_name" in self.table:
            return self.table["display_name"]
        else:
            return self.table["date_start"]

    def set_end_including(self, githash):
        """Change the 'end_including' key to the given git hash."""
        assert "end_including" in self.table
        self.table["end_including"] = githash

    def is_ongoing(self):
        """Is this report 'in progress'?"""
        return self.table.get("ongoing", False)

    def is_derived(self):
        """Is this report 'derived', i.e. generated from data in the other
        reports?
        """
        return self.table.get("derived", False)


class Reports:
    def __init__(self, project_dirname):
        self.project_dirname = project_dirname
        self.filename = os.path.join(project_dirname, "reports.toml")
        with open(self.filename, encoding="utf8") as fp:
            self.doc = tomlkit.load(fp)

        self.reports = {k: Report(v) for k, v in self.doc.items()}
        main_report_names = [
            k for k, v in self.reports.items() if not v.is_derived()
        ]
        self.latest_name = max(main_report_names)

    def get_latest_filename(self):
        latest_filename = os.path.join(
            self.project_dirname, f"{self.latest_name}.toml"
        )
        return latest_filename

    def get_latest_name(self):
        return self.latest_name

    def get_report(self, datestr):
        return Report(self.doc[datestr])

    def get_names(self):
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
        if "fc" in self.ref[1]:
            return self.ref[1]["fc"]
        if "ac" in self.ref[1]:
            return self.ref[1]["ac"]
        return "unknown"

    @property
    def manual_cat(self):
        return self.ref[1]["mc"]

    @property
    def automatic_cat(self):
        """Category of this entry."""
        if "fc" in self.ref[1]:
            return self.ref[1]["fc"]
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

    def remove_highlighted(self):
        del self.ref[1]["ah"]

    def set_highlighted(self):
        self.ref[1]["ah"] = 1

    def set_auto_cat(self, cat, section, pattern):
        self.ref[1]["ac"] = cat
        self.ref[1]["ac_section"] = section
        self.ref[1]["ac_pattern"] = pattern

    def set_fixes_cat(self, cat, reason):
        self.ref[1]["fc"] = cat
        self.ref[1]["fc_reason"] = reason

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

    def is_highlighted(self):
        """Is this entry highlighted?"""
        # If there's a manual judgement, that takes priority
        if "mh" in self.ref[1]:
            if self.ref[1]["mh"] == 1:
                return True
            return False

        if "ah" in self.ref[1] and self.ref[1]["ah"] == 1:
            return True
        return False

    def clear_automatic_annotation(self):
        for key in [
            "ac",
            "ac_pattern",
            "ac_section",
            "ah",
            "fc",
            "fc_reason",
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
