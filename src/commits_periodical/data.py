import collections
import os.path
import pathlib

import toml
import tomlkit

RESERVED_REPORT_NAMES = ["prev"]


class IndexEntry:
    """This is metadata about a single report."""

    def __init__(self, table: tomlkit.items.Table | dict, read_only=True):
        self.table = table
        self.read_only = read_only

    def __contains__(self, key):
        return key in self.table

    def __getitem__(self, key):
        return self.table[key]

    def get(self, key, default=None):
        """Just like dict.get()"""
        return self.table.get(key, default)

    def get_display_name(self):
        if "display_name" in self.table:
            return self.table["display_name"]
        else:
            return self.table["display_date_start"]

    def set_end_including(self, githash):
        """Change the 'end_including' key to the given git hash."""
        assert self.read_only is False
        assert "end_including" in self.table
        self.table["end_including"] = githash

    def is_derived(self):
        """Is this report 'derived', i.e. generated from data in the other
        reports?
        """
        return self.table.get("derived", False)


class Index:
    """This is metadata about all available reports."""

    def __init__(self, project_dirname, read_only=True):
        self.project_dirname = project_dirname
        self.read_only = read_only

        self.filename = os.path.join(project_dirname, "index.toml")
        with open(self.filename, encoding="utf8") as fp:
            if self.read_only:
                self.doc = toml.load(fp)
            else:
                self.doc = tomlkit.load(fp)

        # Check for reserved report names
        for reserved in RESERVED_REPORT_NAMES:
            if reserved in self.doc.keys():
                print(
                    f"Cannot have a report called '{reserved}'; reserved name"
                )
                exit(1)

        self.index_entries = {
            k: IndexEntry(v, self.read_only) for k, v in self.doc.items()
        }
        main_index_entry_names = [
            k for k, v in self.index_entries.items() if not v.is_derived()
        ]
        sorted_names = sorted(main_index_entry_names)
        self.latest_name = sorted_names[-1]
        self.prev_name = sorted_names[-2]

    def get_filename(self, name):
        filename = os.path.join(self.project_dirname, f"{name}.toml")
        return filename

    def get_latest_name(self):
        return self.latest_name

    def get_prev_name(self):
        return self.prev_name

    def get_index_entry(self, report_name):
        return self.index_entries[report_name]

    def get_names(self):
        return self.doc.keys()

    def save(self):
        assert self.read_only is False
        out = tomlkit.dumps(self.doc)
        with open(self.filename, "w", encoding="utf8") as fp:
            fp.write(out)


class ReportEntry:
    """An entry in the report's summaries; may be a single commit or a group of
    commits.
    """

    def __init__(self, ref):
        self.githash = ref[0]
        # Short for "annotation"
        self.ann = ref[1]

    @property
    def cat(self):
        """Category of this entry."""
        if "mc" in self.ann:
            return self.ann["mc"]
        if "fc" in self.ann:
            return self.ann["fc"]
        if "ac" in self.ann:
            return self.ann["ac"]
        return "unknown"

    @property
    def manual_cat(self):
        return self.ann["mc"]

    @property
    def automatic_cat(self):
        """Category of this entry."""
        if "fc" in self.ann:
            return self.ann["fc"]
        if "ac" in self.ann:
            return self.ann["ac"]
        return "unknown"

    def has_manual_cat(self):
        return "mc" in self.ann

    def has_auto_cat(self):
        return "ac" in self.ann

    def has_fixed_cat(self):
        return "fc" in self.ann

    def get_auto_cat(self):
        return self.ann["ac"]

    def get_auto_reasons(self):
        return self.ann["ac_section"], self.ann["ac_pattern"]

    def get_fixed_cat(self):
        return self.ann["fc"]

    def get_fixed_reason(self):
        return self.ann["fc_reason"]

    def set_group(self, group):
        self.ann["g"] = group

    def has_group(self):
        return "g" in self.ann

    def groupname(self):
        return self.ann["g"]

    def is_cat_disputed(self):
        if "mc" not in self.ann:
            return False
        if self.automatic_cat != self.manual_cat:
            return True
        return False

    def remove_highlighted(self):
        del self.ann["ah"]

    def set_highlighted(self):
        self.ann["ah"] = 1

    def set_auto_cat(self, cat, section, pattern):
        # Sanity check: we shouldn't be re-setting the cat
        if "ac" in self.ann and self.ann["ac"] != cat:
            raise ValueError(
                f"Trying to set already-set entry.  Old, new:\n"
                f"{self.ann['ac_section']}\t{self.ann['ac']}\t{self.ann['ac_pattern']}\n"
                f"{section}\t{cat}\t{pattern}"
            )
        # Set cat
        self.ann["ac"] = cat
        self.ann["ac_section"] = section
        self.ann["ac_pattern"] = pattern

    def set_fixes_cat(self, cat, reason):
        self.ann["fc"] = cat
        self.ann["fc_reason"] = reason

    def is_revert(self):
        if "ac" in self.ann and self.ann["ac"] == "reverts":
            return True
        return False

    def is_highlighted(self):
        """Is this entry highlighted?"""
        # If there's a manual judgement, that takes priority
        if "mh" in self.ann:
            if self.ann["mh"] == 1:
                return True
            return False

        if "ah" in self.ann and self.ann["ah"] == 1:
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
            if key in self.ann:
                del self.ann[key]

    def backup_auto(self):
        if "ac" in self.ann:
            self.ann["_ac"] = self.ann["ac"]

    def get_backup_auto(self):
        return self.ann.get("_ac", False)

    def clear_backup_auto(self):
        if "_ac" in self.ann:
            del self.ann["_ac"]


class Report:
    """A document which details all commits within a range."""

    def __init__(self, filename, read_only=True):
        self.filename = filename
        self.read_only = read_only

        if self.read_only:
            self.doc = {}
        else:
            self.doc = tomlkit.document()
        if self.filename:
            self.load(filename)
        else:
            self._update_data()

    def load(self, filename, start_after=None, end_including=None):
        # Create the file if it doesn't exist
        if not self.read_only:
            if not os.path.exists(filename):
                pathlib.Path(filename).touch()

        # Read the file
        with open(filename, encoding="utf8") as fp:
            if self.read_only:
                doc = toml.load(fp)
            else:
                doc = tomlkit.load(fp)

        # Trim based on start_after and end_including, if relevant
        keys = list(doc.keys())
        if start_after and start_after in doc:
            index = keys.index(start_after)
            keys = keys[index + 1 :]
        if end_including and end_including in doc:
            index = keys.index(end_including)
            keys = keys[: index + 1]

        for key in keys:
            if key in self.doc:
                raise ValueError(f"{key} in multiple documents!")
            value = doc[key]
            self.doc[key] = value
        self._update_data()

    def _update_data(self):
        self.entries = {item[0]: ReportEntry(item) for item in self.doc.items()}
        self.groups = collections.defaultdict(list)
        for entry in self.entries.values():
            if entry.has_group():
                self.groups[entry.groupname()].append(entry)

    def save(self):
        """Save the document to disk."""
        assert self.read_only is False
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
        self.entries[githash] = ReportEntry((githash, commit))

    def clear_automatic_annotations(self):
        for githash in self.get_hashes():
            self.entries[githash].clear_automatic_annotation()
        self.groups.clear()

    def backup_auto(self):
        for githash in self.get_hashes():
            self.entries[githash].backup_auto()

    def clear_backup_auto(self):
        for githash in self.get_hashes():
            self.entries[githash].clear_backup_auto()
