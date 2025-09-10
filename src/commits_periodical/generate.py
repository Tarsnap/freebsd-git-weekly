import collections
import datetime
import html
import re

import commits_periodical
import commits_periodical.data
import commits_periodical.gitlayer
import commits_periodical.html_templates
import commits_periodical.utils


split_into_words = re.compile(r"(\s+)")


def linkify(text):
    words = split_into_words.split(text)
    for i, word in enumerate(words):
        if word.startswith("https://"):
            words[i] = f'<a href="{word}">{word}</a>'
    text = "".join(words)
    return text


def get_commit_long(templates, githash, gitcommit, nostrip=False):
    """Get HTML for a commit."""
    long = gitcommit.message
    author = gitcommit.author
    authordate = datetime.datetime.utcfromtimestamp(gitcommit.authored_date)

    text = commits_periodical.utils.commit_text_display(long, nostrip)

    url = templates.HTML_COMMIT_TAGLINE % (githash, githash, author, authordate)

    # We don't want to end with a \n
    text = html.escape(text).rstrip()
    text = linkify(text)
    if text:
        text = f"<pre>{text}</pre>"
    return url, text


def commit_text(templates, repo, week, item, is_emph, debug):
    """Get a commit message, formatted as HTML."""
    name, entry = item
    if entry.has_group() and not is_emph:
        return commit_group_text(templates, repo, week, item)
    githash = name

    gitcommit = repo.get_commit(githash)
    short = gitcommit.summary

    url, text = get_commit_long(templates, githash, gitcommit)
    inner = templates.HTML_DETAILS_INNER % (text, url)
    out = templates.HTML_DETAILS_OUTER % (html.escape(short), inner)

    if debug and "ac" in entry.ref[1]:
        section = entry.ref[1]["ac_section"]
        pattern = entry.ref[1]["ac_pattern"]
        text = '<p class="debug">'
        text += "debug: classified in "
        # Don't end this sentence with a period; that's too easy to confuse
        # with a regex.
        text += f"<code>{section}</code> by '<code>{pattern}</code>'</p>"
        out = out.replace("</details>", f"{text}</details>")

    if entry.is_cat_disputed():
        if debug:
            out = out.replace("<details>", '<details class="debug">')
            ac = entry.automatic_cat
            mc = entry.manual_cat
            text = '<p class="debug">'
            text += f'debug: Commit manually moved from "{ac}" to "{mc}".</p>'
            out = out.replace("</details>", f"{text}</details>")
    # if debug:
    #    reason = entry.cat_reason()
    #    text = f'<p class="debug">debug: Commit classified by {reason}.</p>'
    #    out = out.replace("</details>", f"{text}</details>")

    return out


def commit_group_text(templates, repo, week, item):
    """Generate HTML for a commit group."""
    name, entry = item
    owns = week.groups[entry.groupname()]

    if owns[0] in commit_group_text.seen:
        return ""

    if owns[0].cat == "reverts" and len(owns) == 2:
        assert owns[1].cat == "reverts"

        gitcommit1 = repo.get_commit(owns[0].githash)
        summary = f"Commit & revert pair: {gitcommit1.summary}"
    else:
        # Strip the number from the groupname
        name = owns[0].groupname()[:-3]
        summary = f"Commit group #{commit_group_text.num_generic}: {name}"
        commit_group_text.num_generic += 1

    inner = ""
    for i, entry in enumerate(owns):
        gitcommit = repo.get_commit(entry.githash)
        url, text = get_commit_long(
            templates, entry.githash, gitcommit, nostrip=True
        )
        if i > 0:
            inner += "<hr>"
        inner += templates.HTML_DETAILS_INNER % (text, url)
    out = templates.HTML_DETAILS_OUTER % (summary, inner)

    # record that we've handled these already
    commit_group_text.seen.extend(owns)
    return out


# FIXME: hack
commit_group_text.seen = []
commit_group_text.num_generic = 0


def split_into_categories(doc):
    """Get a dict containing per-category entries."""
    cats = collections.defaultdict(list)
    for item in doc.get_entries():
        _, entry = item
        if entry.is_style():
            cats["style"].append(item)
        else:
            cats[entry.cat].append(item)

    # Make extra copies of "emphasized" commits
    for item in doc.get_entries():
        _, entry = item
        if entry.is_emphasized():
            cats["emph"].append(item)
    return cats


def make_table_classification(project, cats, total_commits):
    num_in_groups = 0
    num_manual = 0  # this is for totally manual, i.e. not disputed
    reason_totals = collections.defaultdict(int)
    disputed_totals = collections.defaultdict(int)

    # Count mis-classified and un-classified
    for cat, entries in cats.items():
        # Don't count emphasized commits (they're copies)
        if cat == "emph":
            continue

        for _, entry in entries:
            if "ac_section" in entry.ref[1]:
                ac_section = entry.ref[1]["ac_section"]
                reason_totals[ac_section] += 1

                if entry.is_cat_disputed():
                    disputed_totals[ac_section] += 1
            elif "mc" in entry.ref[1]:
                num_manual += 1

            if entry.has_group():
                num_in_groups += 1
    # for s in sorted(reason_totals.keys()):
    #    print("%s\t%i\t%i" % (s, reason_totals[s], disputed_totals[s]))

    def table_row(num, total_commits, text, disputed=None):
        perc = f"{100 * num / total_commits:.1f}%"
        out = f"<tr><td>{num}</td><td>{perc}</td>"
        if disputed is not None:
            out += f"<td>{disputed}</td>"
        out += f"<td>{text}</td></tr>"
        return out

    num_unknown = total_commits - sum(reason_totals.values()) - num_manual
    num_misclassified = sum(disputed_totals.values())

    # Display that data
    section = '<div class="debug">'
    section += "<p>debug: info about the automatic classification</p>"
    section += "<table>"
    section += (
        "<tr><th>num</th><th>%</th><th>num changed</th><th>stage</th></tr>"
    )
    for reason in sorted(reason_totals.keys()):
        section += table_row(
            reason_totals[reason],
            total_commits,
            reason,
            disputed_totals[reason],
        )
    section += table_row(
        num_manual, total_commits, "Manually-classified commits", 0
    )
    section += table_row(num_unknown, total_commits, "Unclassified commits", 0)
    section += "</table>"

    section += "<p>debug: more stats</p>"

    section += "<table>"
    section += "<tr><th>num</th><th>%</th><th>stage</th></tr>"
    section += table_row(
        num_misclassified, total_commits, "Misclassified commits"
    )
    section += table_row(
        total_commits - num_misclassified - num_manual,
        total_commits,
        "Classified commits, no corrections",
    )
    section += "</table>"
    section += "<p>debug: groups</p>"
    section += "<table>"
    section += table_row(num_in_groups, total_commits, "Commits in groups")
    section += "</table>"
    section += "</div>"
    return section


def make_preamble(project, cats, debug):
    """Generate the 'preamble' section."""
    section = "<section>"
    section += "<p>Table of contents and commits per category:</p>"
    section += "<table>"
    total_commits = 0
    for cat, entries in cats.items():
        # Don't count emphasized commits (they're copies)
        if cat == "emph":
            continue
        total_commits += len(entries)

    for cat, catinfo in project.categories.items():
        section_name, intro_text = catinfo
        if not section_name:
            continue

        relevant = cats[cat]
        num = len(relevant)
        perc = f"{100 * num / total_commits:.1f}%"
        # Hack to show a difference between "emphasized" and the rest
        if cat == "userland":
            section += f'<tr class="top-line"><td>{num}</td><td>{perc}</td>'
        elif cat == "emph":
            section += f'<tr class="top-line"><td>({num})</td><td></td>'
        else:
            section += f"<tr><td>{num}</td><td>{perc}</td>"
        link = f'<a href="#{cat}">{section_name}</a>'
        if cat == "emph":
            link += " (these are copies, not in stats)"

        section += f"<td>{link}</td></tr>"

    section += f"""<tr class="top-line">
        <td>{total_commits}</td>
        <td>100%</td>
        <td>total</td></tr>"""
    section += """<tr class="top-line"><td></td><td></td>
    <td><a href="#technical-notes">Technical notes about this page</a></td></tr>
    """
    section += "</table>\n"

    if debug:
        section += make_table_classification(project, cats, total_commits)

    section += "</section>"
    return section


def make_section(
    templates, repo, week, cats, cat, section_title, intro_text, debug
):
    """Generate HTML for a normal section."""
    if cat == "quit":
        return None
    if section_title is None:
        return None
    is_emph = cat == "emph"
    section = f"<section id='{cat}'>"
    section += templates.HTML_SECTION % (section_title, cat, cat)
    if intro_text:
        section += f"<p>{intro_text}</p>"
    relevant = cats[cat]
    for item in relevant:
        section += commit_text(templates, repo, week, item, is_emph, debug)
    if len(relevant) == 0:
        section += "<p>-- no commits in this category this week --</p>"
    section += "</section>"
    return section


def generate_period(repo, doc, project, datestr, debug):
    """Generate HTML for the latest week."""
    templates = commits_periodical.html_templates.HtmlTemplates()

    filename_out = doc.filename.replace("freebsd/", "out/").replace(
        ".toml", ".html"
    )
    if debug:
        filename_out = filename_out.replace(".html", "-debug.html")
    print(f"Generating HTML for {doc.filename} in {filename_out}")

    # Split into categories
    cats = split_into_categories(doc)

    # Add preamble
    sections = []
    enddatestr = (
        datetime.datetime.strptime(datestr, "%Y-%m-%d")
        + datetime.timedelta(days=6)
    ).strftime("%Y-%m-%d")
    intro = templates.INTRO_SECTION % (datestr, enddatestr)
    if debug:
        intro += templates.INTRO_DEBUG_MESSAGE
    sections.append(intro)
    section = make_preamble(project, cats, debug)
    sections.append(section)

    # Handle each category
    for cat, catinfo in project.categories.items():
        section_title, intro_text = catinfo
        section = make_section(
            templates, repo, doc, cats, cat, section_title, intro_text, debug
        )
        if section:
            sections.append(section)

    # Add technical notes
    sections.append(templates.TECHNICAL_NOTES_SECTION)

    out = templates.html_begin % (datestr, datestr)
    for section in sections:
        out += section

    if debug:
        url = f"{datestr}.html"
        text = datestr
    else:
        url = f"{datestr}-debug.html"
        text = f"{datestr} (debug)"
    version = commits_periodical.__version__
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    out += templates.RELEASE_DEBUG % (version, now, url, text)

    out += templates.HTML_END

    with open(filename_out, "w", encoding="utf8") as fp:
        fp.write(out)


def generate_index(metadata_file):
    templates = commits_periodical.html_templates.HtmlTemplates()

    start_dates = sorted(metadata_file.get_start_dates())

    weeks = "<ul>"
    for i, start_date in enumerate(start_dates):
        weeks += "<li>"
        if i < len(start_dates) - 1:
            weeks += f'<a href="{start_date}.html">{start_date}</a>'
        else:
            weeks += "no 'release' version yet"
        weeks += " (additional info in the "
        weeks += f' <a href="{start_date}-debug.html">debug version</a>)'
        weeks += "</li>"
    weeks += "</ul>"

    out = templates.index % (weeks)

    filename_out = "out/index.html"
    with open(filename_out, "w", encoding="utf8") as fp:
        fp.write(out)
