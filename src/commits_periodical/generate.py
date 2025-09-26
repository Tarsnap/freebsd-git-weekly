import collections
import datetime
import html
import os.path
import re
import sys

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


def commit_debug_info(entry):
    text = ""
    if entry.has_auto_cat():
        section, pattern = entry.get_auto_reasons()
        text += '<p class="debug">'
        text += "debug: classified in "
        # Don't end this sentence with a period; that's too easy to confuse
        # with a regex.
        text += f"<code>{section}</code> by '<code>{pattern}</code>'</p>"

    if entry.is_cat_disputed():
        ac = entry.automatic_cat
        mc = entry.manual_cat
        text += '<p class="debug">'
        text += f'debug: Commit manually moved from "{ac}" to "{mc}".</p>'

    return text


def commit_text(templates, repo, report, item, is_high, debug):
    """Get a commit message, formatted as HTML."""
    name, entry = item
    if entry.has_group() and not is_high:
        return commit_group_text(templates, repo, report, item, debug)
    githash = name

    gitcommit = repo.get_commit(githash)
    short = gitcommit.summary

    url, text = get_commit_long(templates, githash, gitcommit)
    inner = templates.HTML_DETAILS_INNER % (text, url)
    out = templates.HTML_DETAILS_OUTER % (html.escape(short), inner)

    if debug:
        text = commit_debug_info(entry)
        out = out.replace("</details>", f"{text}\n</details>")

        # add overall colour to the commit display
        if entry.is_cat_disputed():
            out = out.replace("<details>", '<details class="debug">')

    return out


def commit_group_text(templates, repo, report, item, debug):
    """Generate HTML for a commit group."""
    name, entry = item
    owns = report.groups[entry.groupname()]

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

        if debug:
            inner += commit_debug_info(entry)
    out = templates.HTML_DETAILS_OUTER % (summary, inner)

    if debug and entry.has_fixed_cat():
        fc = entry.get_fixed_cat()
        reason = entry.get_fixed_reason()
        text = '<p class="debug">'
        text += "debug: moved to "
        # Don't end this sentence with a period; that's too easy to confuse
        # with a regex.
        text += f"<code>{fc}</code> because '<code>{reason}</code>'</p>"
        out = out.replace("</details>", f"{text}</details>")

    # record that we've handled these already
    commit_group_text.seen.extend(owns)
    return out


# FIXME: hack
commit_group_text.seen = []
commit_group_text.num_generic = 0


def split_into_categories(doc, only_show):
    """Get a dict containing per-category entries."""
    cats = collections.defaultdict(list)
    for item in doc.get_entries():
        _, entry = item
        if not only_show or (only_show and entry.cat in only_show):
            cats[entry.cat].append(item)

    # Make extra copies of "highlighted" commits
    if not only_show or "highlight" in only_show:
        for item in doc.get_entries():
            _, entry = item
            if entry.is_highlighted():
                cats["highlight"].append(item)

    return cats


def make_table_classification(cats, total_commits):
    num_in_groups = 0
    num_manual = 0  # this is for totally manual, i.e. not disputed
    reason_totals = collections.defaultdict(int)
    disputed_totals = collections.defaultdict(int)
    num_group_consecutive = 0
    num_group_reverts = 0
    num_group_fixes = 0

    # Count mis-classified and un-classified
    for cat, entries in cats.items():
        # Don't count highlighted commits (they're copies)
        if cat == "highlight":
            continue

        for _, entry in entries:
            if entry.has_auto_cat():
                ac_section, _ = entry.get_auto_reasons()
                reason_totals[ac_section] += 1

                if entry.is_cat_disputed():
                    disputed_totals[ac_section] += 1
            elif entry.has_manual_cat():
                num_manual += 1

            if entry.has_group():
                num_in_groups += 1
                if entry.groupname().startswith("revert-pair"):
                    num_group_reverts += 1
                elif entry.has_fixed_cat():
                    num_group_fixes += 1
                else:
                    num_group_consecutive += 1

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
        total_commits - num_misclassified - num_manual - num_unknown,
        total_commits,
        "Classified commits, no corrections",
    )
    section += "</table>"
    section += "<p>debug: groups</p>"
    section += "<table>"
    section += table_row(num_group_reverts, total_commits, "num in revert")
    section += table_row(num_group_fixes, total_commits, "num in fixes")
    section += table_row(
        num_group_consecutive, total_commits, "num in consecutive"
    )
    section += table_row(num_in_groups, total_commits, "Commits in groups")
    section += "</table>"
    section += "</div>"
    return section


def make_preamble(project, cats, debug, only_show):
    """Generate the 'preamble' section."""
    section = "<section>"
    section += "<p>Table of contents and commits per category:</p>"
    section += "<table>"
    total_commits = 0
    for cat, entries in cats.items():
        # Don't count highlighted commits (they're copies)
        if cat == "highlight":
            continue
        total_commits += len(entries)

    # Special case: override the above if we only have "highlight".
    if len(cats.keys()) == 1 and "highlight" in cats:
        total_commits = len(cats["highlight"])

    for cat, catinfo in project.categories.items():
        if only_show:
            if cat not in only_show:
                continue

        section_name, _ = catinfo
        if not section_name:
            continue

        relevant = cats[cat]
        num = len(relevant)
        perc = f"{100 * num / total_commits:.1f}%"
        # Hack to show a difference between "highlight" and the rest
        if cat == "userland":
            section += f'<tr class="top-line"><td>{num}</td><td>{perc}</td>'
        elif cat == "highlight":
            section += f'<tr class="top-line"><td>({num})</td><td></td>'
        else:
            section += f"<tr><td>{num}</td><td>{perc}</td>"
        link = f'<a href="#{cat}">{section_name}</a>'
        if cat == "highlight":
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
        section += make_table_classification(cats, total_commits)

    section += "</section>"
    return section


def make_section(
    templates, repo, report, cats, cat, section_title, intro_text, debug
):
    """Generate HTML for a normal section."""
    if cat == "quit":
        return None
    if section_title is None:
        return None
    is_high = cat == "highlight"
    section = f"<section id='{cat}'>"
    section += templates.HTML_SECTION % (section_title, cat, cat)
    if intro_text:
        section += f"<p>{intro_text}</p>"
    relevant = cats[cat]
    for item in relevant:
        section += commit_text(templates, repo, report, item, is_high, debug)
    if len(relevant) == 0:
        section += "<p>-- no commits in this category this week --</p>"
    section += "</section>"
    return section


def generate_period(
    repo,
    doc,
    project,
    index_entry,
    debug,
    project_dirname,
    reproducible,
    index_entry_name,
):
    """Generate HTML for the latest report."""
    if index_entry.get("ongoing") and not debug:
        print("Refusing to generate 'release' HTML for ongoing")
        sys.exit(0)

    templates = commits_periodical.html_templates.HtmlTemplates()

    filename_out = os.path.join(
        project_dirname.replace("projects/", "out/"), f"{index_entry_name}.html"
    )
    if debug:
        filename_out = filename_out.replace(".html", "-debug.html")
    print(f"Generating HTML for {doc.filename} in {filename_out}")

    # Load extra data (if applicable)
    if "include_spans" in index_entry:
        for span in index_entry["include_spans"]:
            span_filename = os.path.join(project_dirname, f"{span}.toml")
            cache_filename = span_filename.replace(".toml", ".gitcache")
            doc.load(span_filename)
            repo.add_cache(cache_filename)

    # Split into categories
    only_show = index_entry.get("only_show", False)
    cats = split_into_categories(doc, only_show)

    # Add preamble
    sections = []
    date_start = index_entry["date_start"]
    date_end = index_entry["date_end"]
    intro = templates.INTRO_SECTION % (date_start, date_end)
    if debug:
        intro += templates.INTRO_DEBUG_MESSAGE

    if index_entry.get("ongoing"):
        text = '<p class="debug">This report is still in progress.</p>'
        intro = intro.replace("</section>", f"{text}</section>")

    sections.append(intro)
    section = make_preamble(project, cats, debug, only_show)
    sections.append(section)

    # Handle each category
    for cat, catinfo in project.categories.items():
        if only_show:
            if cat not in only_show:
                continue
        section_title, intro_text = catinfo
        section = make_section(
            templates, repo, doc, cats, cat, section_title, intro_text, debug
        )
        if section:
            sections.append(section)

    # Add technical notes
    sections.append(templates.TECHNICAL_NOTES_SECTION)

    date_period = f"{date_start} to {date_end}"
    out = templates.html_begin % (date_period, date_period)
    for section in sections:
        out += section

    if debug:
        url = f"{date_start}.html"
        text = date_start
        alternate_version = f'Alternate version: <a href="{url}">{text}</a>'
        alternate_version += " (release)"
    else:
        url = f"{date_start}-debug.html"
        text = f"{date_start} (debug)"
        alternate_version = f'Alternate version: <a href="{url}">{text}</a>'
        alternate_version += " (contains info about the classification)"
    version = commits_periodical.__version__
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    if reproducible:
        now = "(time removed for reproducibility)"
    out += templates.RELEASE_DEBUG % (version, now, alternate_version)

    out += templates.HTML_END

    with open(filename_out, "w", encoding="utf8") as fp:
        fp.write(out)


def index_table(index, start_dates):
    out = "<table>"
    out += "<tr><th>Report</th>"
    out += "<th>Report with extra info about classification</th></tr>"
    for start_date in start_dates:
        index_entry = index.get_index_entry(start_date)
        display_name = index_entry.get_display_name()
        out += "<tr>"
        out += "<td>"
        if not index_entry.get("ongoing"):
            out += f'<a href="{start_date}.html">{display_name}</a>'
        else:
            out += f"{display_name}: in progress"
        out += "</td>"
        out += "<td>"
        out += f'<a href="{start_date}-debug.html">{display_name} (debug)</a>'
        out += "</td>"
        out += "</tr>"
    out += "</table>"
    return out


def generate_index(project_dirname, index):
    filename_out = os.path.join(
        project_dirname.replace("projects", "out"), "index.html"
    )
    print(f"Generating index in {filename_out}")

    templates = commits_periodical.html_templates.HtmlTemplates()

    index_entry_names = sorted(index.get_names())
    regular = []
    alternate = []
    for index_entry_name in index_entry_names:
        index_entry = index.get_index_entry(index_entry_name)
        if index_entry.is_derived():
            alternate.append(index_entry_name)
        else:
            regular.append(index_entry_name)

    regular_reports = index_table(index, regular)
    alternates = index_table(index, alternate)

    out = templates.index % (regular_reports, alternates)

    with open(filename_out, "w", encoding="utf8") as fp:
        fp.write(out)
