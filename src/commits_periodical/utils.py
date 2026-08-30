"""Helper functions for freebsd-git-weekly."""

import re
import tomllib

import commits_periodical.gitlayer

LINK_PROBLEM_REPORT = "https://bugs.freebsd.org/bugzilla/show_bug.cgi?id=%s"

LINK_COMMIT = "https://cgit.freebsd.org/src/commit/?id=%s"

_PR_NUM_RE = re.compile(r"\d+")
_FIXES_PAREN_RE = re.compile(r"^(Fixes:\s+[0-9a-fA-F]{6,})\(")
_FIXES_HASH_RE = re.compile(r"\b[0-9a-fA-F]{6,}\b")


def read_toml(filename: str) -> dict:
    """Read a toml file (read-only)."""
    with open(filename, "rb") as fp:
        doc = tomllib.load(fp)
    return doc


def get_summary_prefix(commit: commits_periodical.gitlayer.CachedCommit) -> str:
    """Get the commit summary, but only up to the first colon."""
    out = commit.summary
    # Only take up to the first colon
    out = out.split(":", 1)[0]
    return out


def commit_text_display(text: str, nostrip: bool = False) -> str:
    """Format a git commit message for display."""
    outlines = []
    # Strip the summary as well
    if nostrip:
        lines = text.splitlines()
    else:
        # Skip the summary line and the following blank line
        lines = text.splitlines()[2:]
    for line in lines:
        if line.startswith("PR:"):
            line = _PR_NUM_RE.sub(
                lambda x: LINK_PROBLEM_REPORT % (int(x.group())), line
            )
        if line.startswith("Fixes:"):
            # Fix a lack of space between the hash and a parenthesis.
            # Do this before linkifying it.
            line = _FIXES_PAREN_RE.sub(r"\1 (", line)
            # Linkify the git hash.
            line = _FIXES_HASH_RE.sub(lambda x: LINK_COMMIT % (x.group()), line)

        outlines.append(line)

    out = "\n".join(outlines) + "\n"
    return out
