import collections
import os.path
import pathlib

# We normally don't allow "from", but in this case it's worth it.
from typing import Any

import toml
import tomlkit

RESERVED_REPORT_NAMES = ["prev", "all"]


class IndexEntry:
    """This is metadata about a single report."""

    def __init__(
        self, table: tomlkit.items.Table | dict, read_only: bool = True
    ) -> None:
        self.table = table
        self.read_only = read_only

    def __contains__(self, key: str) -> bool:
        return key in self.table

    def __getitem__(self, key: str) -> Any:
        return self.table[key]

    def get(self, key: str, default: Any = None) -> Any:
        """Just like dict.get()"""
        return self.table.get(key, default)

    def get_display_name(self) -> str:
        if "display_name" in self.table:
            return self.table["display_name"]
        else:
            return self.table["display_date_start"]

    def set_end_including(self, githash: str) -> None:
        """Change the 'end_including' key to the given git hash."""
        if self.read_only:
            raise ValueError("Cannot modify a read-only IndexEntry")
        if "end_including" not in self.table:
            raise ValueError("No 'end_including' in table")

        self.table["end_including"] = githash

    def remove_ongoing(self) -> None:
        """Remove the 'ongoing' key."""
        del self.table["ongoing"]

    def is_derived(self) -> bool:
        """Is this report 'derived', i.e. generated from data in the other
        reports?
        """
        return self.table.get("derived", False)


class Index:
    """This is metadata about all available reports."""

    def __init__(self, project_dirname: str, read_only: bool = True) -> None:
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
                msg = f"Cannot have a report called '{reserved}'; reserved name"
                raise KeyError(msg)

        self.index_entries = {
            k: IndexEntry(v, self.read_only) for k, v in self.doc.items()
        }
        main_index_entry_names = [
            k for k, v in self.index_entries.items() if not v.is_derived()
        ]
        self.sorted_main_names = sorted(main_index_entry_names)
        if len(self.sorted_main_names) == 0:
            raise KeyError("We need at least one non-derived report")
        self.latest_name = self.sorted_main_names[-1]

        self.prev_name: str | None
        if len(self.sorted_main_names) >= 2:
            self.prev_name = self.sorted_main_names[-2]
        else:
            self.prev_name = None

    def get_filename(self, name: str) -> str:
        filename = os.path.join(self.project_dirname, f"{name}.toml")
        return filename

    def get_latest_name(self) -> str:
        return self.latest_name

    def get_prev_name(self) -> str:
        if self.prev_name is None:
            raise KeyError("We don't have enough reports to have a 'prev'")
        return self.prev_name

    def _make_all_entry(self) -> IndexEntry:
        first = self.index_entries[self.sorted_main_names[0]]
        last = self.index_entries[self.sorted_main_names[-1]]
        # This is a temporary IndexEntry, not stored in the file
        ie = IndexEntry(
            {
                "derived": True,
                "display_name": "all",
                "display_date_start": first["display_date_start"],
                "display_date_end": last["display_date_end"],
                "include_spans": self.sorted_main_names,
                "start_after": first["start_after"],
                "end_including": last["end_including"],
            }
        )
        return ie

    def get_index_entry(self, report_name: str) -> IndexEntry:
        # Special-case for "all" report
        if report_name == "all":
            return self._make_all_entry()
        elif report_name == "prev":
            raise KeyError("Index.get_index_entry() does not support 'prev'")
        return self.index_entries[report_name]

    def get_names(self) -> collections.abc.KeysView[str]:
        return self.doc.keys()

    def add_index_entry_after(
        self, name: str, data: dict, previous_name: str
    ) -> None:
        # This is more complicated than it should be, but it works with
        # tomlkit 0.15.1.  This function doesn't stick to the public API,
        # and thus might break in the future.
        assert isinstance(self.doc, tomlkit.TOMLDocument)

        # Sanity checks
        if name in self.doc:
            raise KeyError(f"{name} already exists in toml file")
        if previous_name not in self.doc:
            raise KeyError(f"Couldn't find {previous_name} in toml file")

        # Create the TOML table item
        new_table = tomlkit.table()
        for k, v in data.items():
            new_table[k] = v
        # _insert_after() doesn't add a blank line after the new table
        new_table.add(tomlkit.nl())

        # Insert it
        self.doc._insert_after(previous_name, name, new_table)

    def save(self) -> None:
        if self.read_only:
            raise ValueError("Cannot modify a read-only Index")

        out = tomlkit.dumps(self.doc)
        with open(self.filename, "w", encoding="utf8") as fp:
            fp.write(out)


class ReportEntry:
    """An entry in the report's summaries; may be a single commit or a group of
    commits.
    """

    def __init__(self, ref: tuple[str, tomlkit.items.Table | dict]) -> None:
        self.githash = ref[0]
        # Short for "annotation"
        self.ann = ref[1]

    def __str__(self) -> str:
        out = self.githash + "\n"
        out += "\n".join(f"  {k}: {v}" for k, v in self.ann.items())
        return out

    @property
    def cat(self) -> str:
        """Category of this entry."""
        if "mc" in self.ann:
            return self.ann["mc"]
        if "fc" in self.ann:
            return self.ann["fc"]
        if "ac" in self.ann:
            return self.ann["ac"]
        return "unknown"

    @property
    def manual_cat(self) -> str:
        return self.ann["mc"]

    @property
    def automatic_cat(self) -> str:
        """Category of this entry."""
        if "fc" in self.ann:
            return self.ann["fc"]
        if "ac" in self.ann:
            return self.ann["ac"]
        return "unknown"

    def has_manual_cat(self) -> bool:
        return "mc" in self.ann

    def has_auto_cat(self) -> bool:
        return "ac" in self.ann

    def has_fixed_cat(self) -> bool:
        return "fc" in self.ann

    def get_auto_cat(self) -> str:
        return self.ann["ac"]

    def get_auto_reasons(self) -> tuple[str, str]:
        return self.ann["ac_section"], self.ann["ac_pattern"]

    def get_fixed_cat(self) -> str:
        return self.ann["fc"]

    def get_fixed_reason(self) -> str:
        return self.ann["fc_reason"]

    def set_group(self, group: str) -> None:
        self.ann["g"] = group

    def has_group(self) -> bool:
        return "g" in self.ann

    def groupname(self) -> str:
        return self.ann["g"]

    def is_cat_disputed(self) -> bool:
        if "mc" not in self.ann:
            return False
        if self.automatic_cat != self.manual_cat:
            return True
        return False

    def remove_highlighted(self) -> None:
        del self.ann["ah"]

    def set_highlighted(self) -> None:
        self.ann["ah"] = 1

    def set_auto_cat(self, cat: str, section: str, pattern: str) -> None:
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

    def set_fixes_cat(self, cat: str, reason: str) -> None:
        self.ann["fc"] = cat
        self.ann["fc_reason"] = reason

    def is_revert(self) -> bool:
        if "ac" in self.ann and self.ann["ac"] == "reverts":
            return True
        return False

    def is_highlighted(self) -> bool:
        """Is this entry highlighted?"""
        # If there's a manual judgement, that takes priority
        if "mh" in self.ann:
            if self.ann["mh"] == 1:
                return True
            return False

        if "ah" in self.ann and self.ann["ah"] == 1:
            return True
        return False

    def clear_automatic_annotation(self) -> None:
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

    def backup_auto(self) -> None:
        if "ac" in self.ann:
            self.ann["_ac"] = self.ann["ac"]

    def get_backup_auto(self) -> str | None:
        return self.ann.get("_ac", None)

    def clear_backup_auto(self) -> None:
        if "_ac" in self.ann:
            del self.ann["_ac"]


class Report:
    """A document which details all commits within a range."""

    def __init__(self, filename: str | None, read_only: bool = True) -> None:
        self.filename = filename
        self.read_only = read_only

        self.doc: tomlkit.items.Table | dict
        if self.read_only:
            self.doc = {}
        else:
            self.doc = tomlkit.document()
        if self.filename:
            self.load(self.filename)
        else:
            self._update_data()

    def load(
        self,
        filename: str,
        start_after: str | None = None,
        end_including: str | None = None,
    ) -> None:
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

    def _update_data(self) -> None:
        self.entries = {item[0]: ReportEntry(item) for item in self.doc.items()}
        self.groups = collections.defaultdict(list)
        for entry in self.entries.values():
            if entry.has_group():
                self.groups[entry.groupname()].append(entry)

    def save(self) -> None:
        """Save the document to disk."""
        if self.read_only:
            raise ValueError("Cannot modify a read-only Report")
        if self.filename is None:
            raise ValueError("API error; should have a filename")

        out = tomlkit.dumps(self.doc)
        with open(self.filename, "w", encoding="utf8") as fp:
            fp.write(out)

    def get_entries(self) -> collections.abc.Iterator[tuple[str, ReportEntry]]:
        """Generator to return each commit."""
        yield from self.entries.items()

    def get_hashes(self) -> collections.abc.Iterator[str]:
        """Get all hashes."""
        yield from self.entries

    def get_entry(self, githash: str) -> ReportEntry:
        return self.entries[githash]

    def _get_groupname(self, basename: str) -> str:
        """Get a name to distinguish a new group of commits."""
        groupnum = 0
        while True:
            groupname = f"{basename}-{groupnum:02d}"
            if groupname not in self.groups:
                break
            groupnum += 1

            # Panic if we've looped too much
            if groupnum > 99:
                raise ValueError(f"Too many groups with basename '{basename}'")

        return groupname

    def set_group(
        self, githashes: list[str], basename: str, groupname: str | None = None
    ) -> None:
        if not groupname:
            groupname = self._get_groupname(basename)
        self.groups[groupname] = [self.entries[h] for h in githashes]

        for githash in githashes:
            self.entries[githash].set_group(groupname)

    def add_commit(self, githash: str) -> None:
        """Add a commit."""
        if githash in self.entries:
            raise ValueError(f"{githash} already exists in report")
        commit = tomlkit.table()
        self.doc[githash] = commit
        self.entries[githash] = ReportEntry((githash, commit))

    def clear_automatic_annotations(self) -> None:
        for githash in self.get_hashes():
            self.entries[githash].clear_automatic_annotation()
        self.groups.clear()

    def backup_auto(self) -> None:
        for githash in self.get_hashes():
            self.entries[githash].backup_auto()

    def clear_backup_auto(self) -> None:
        for githash in self.get_hashes():
            self.entries[githash].clear_backup_auto()
