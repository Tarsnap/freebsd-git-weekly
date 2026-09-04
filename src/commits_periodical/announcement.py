import commits_periodical.html_templates


def announcement(repo, doc, index_entry):
    templates = commits_periodical.html_templates.HtmlTemplates()

    highlighted_entries = [
        e for _, e in doc.get_entries() if e.is_highlighted()
    ]

    highlighted_lines = []
    for e in highlighted_entries:
        commit = repo.get_commit(e.githash)
        if commit is None:
            raise ValueError(f"commit {e.githash!r} not found in repo cache")
        highlighted_lines.append(f"- {commit.summary}")

    if highlighted_lines:
        highlighted_text = "Highlighted commits:\n\n"
        highlighted_text += "\n".join(highlighted_lines)
        highlighted_text += "\n\n"
        highlighted_text += templates.TEXT_HIGHLIGHTED.substitute().rstrip()
    else:
        highlighted_text = "No highlighted commits this week."

    text = templates.TEXT_ANNOUNCEMENT.substitute(
        date_start=index_entry["display_date_start"],
        date_end=index_entry["display_date_end"],
        display_name=index_entry.get_display_name(),
        num_commits=len(doc.entries),
        highlighted_text=highlighted_text,
    )

    filename = f"out/announce-{index_entry.get_display_name()}.txt"
    with open(filename, "wt", encoding="utf8") as fp:
        fp.write(text)
