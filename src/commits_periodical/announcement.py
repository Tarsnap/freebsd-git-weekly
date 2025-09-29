import commits_periodical.html_templates


def announcement(repo, doc, index_entry):
    templates = commits_periodical.html_templates.HtmlTemplates()

    highlighted_entries = [
        e for _, e in doc.get_entries() if e.is_highlighted()
    ]
    highlighted_lines = [
        f"- {repo.get_commit(e.githash).summary}" for e in highlighted_entries
    ]
    if highlighted_lines:
        highlighted_text = "Highlighted commits:\n\n"
        highlighted_text += "\n".join(highlighted_lines)
        highlighted_text += "\n\n"
        highlighted_text += templates.text_highlighted.rstrip()
    else:
        highlighted_text = "No highlighted commits this week."

    text = templates.text_announcement % (
        index_entry["date_start"],
        index_entry["date_end"],
        index_entry["date_start"],
        index_entry["date_end"],
        index_entry.get_display_name(),
        len(doc.entries),
        highlighted_text,
    )

    filename = f"out/announce-{index_entry.get_display_name()}.txt"
    with open(filename, "wt", encoding="utf8") as fp:
        fp.write(text)
