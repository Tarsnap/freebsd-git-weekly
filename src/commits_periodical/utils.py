import re
import tomllib

LINK_PROBLEM_REPORT = "https://bugs.freebsd.org/bugzilla/show_bug.cgi?id=%s"

LINK_COMMIT = "https://cgit.freebsd.org/src/commit/?id=%s"


def read_toml(filename):
    """Read a toml file (read-only)."""
    with open(filename, "rb") as fp:
        doc = tomllib.load(fp)
    return doc


def get_summary_prefix(commit):
    """Get the commit summary, but only up to the first colon."""
    out = commit.summary
    # Only take up to the first colon
    out = out.split(":")[0]
    return out


def commit_text_display(text, nostrip=False):
    """Format a git commit message for display."""
    out = ""
    # Strip the summary as well
    if nostrip:
        thing = text.splitlines()
    else:
        thing = text.splitlines()[2:]
    for line in thing:
        if line.startswith("PR:"):
            line = re.sub(
                r"\d+", lambda x: LINK_PROBLEM_REPORT % (int(x.group())), line
            )
        if line.startswith("Fixes:"):
            line = re.sub(
                r"\b[0-9a-fA-F]{6,}\b",
                lambda x: LINK_COMMIT % (x.group()),
                line,
            )

        out += line
        out += "\n"
    return out
