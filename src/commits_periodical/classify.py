import collections
import re

import commits_periodical.utils

GROUP_AT_LEAST = 3


def find_highlighted(repo, doc):
    num_changed = 0
    for githash, entry in doc.get_entries():
        if entry.is_revert():
            continue
        if entry.is_highlighted():
            continue
        gitcommit = repo.get_commit(githash)
        if "UPDATING" in gitcommit.modified_files:
            entry.set_highlighted()
            num_changed += 1
            continue
        if gitcommit.summary.startswith("RELNOTES"):
            entry.set_highlighted()
            num_changed += 1
            continue
        if re.search("^Relnotes:", gitcommit.message, re.MULTILINE):
            entry.set_highlighted()
            num_changed += 1
            continue
    if num_changed > 0:
        print(f"Copied {num_changed} commits into 'highlighted'")


def apply_revert(repo, doc, classifier_name, classifier, githash, examine):
    num_changed = 0
    for pattern, cat in classifier.items():
        match = re.search(pattern, examine)
        if not match:
            continue

        prevhash = match.group(1)
        prevcommit = repo.get_commit(prevhash)
        if prevcommit:
            prefix = commits_periodical.utils.get_summary_prefix(prevcommit)
            name = f"revert-pair-{prefix}"
            hashes = [prevhash, githash]
            for githash in hashes:
                entry = doc.entries[githash]
                if not entry.is_revert():
                    entry.set_auto_cat("reverts", classifier_name, pattern)
                    num_changed += 1
                if entry.is_highlighted():
                    entry.remove_highlighted()
        else:
            entry = doc.entries[githash]
            hashes = None
            if not entry.is_revert():
                entry.set_auto_cat("reverts", classifier_name, pattern)
                num_changed += 1
            if entry.is_highlighted():
                entry.remove_highlighted()
        if hashes:
            for githash in hashes:
                if not doc.entries[githash].has_group():
                    doc.set_group(hashes, name)

    return num_changed


def apply_classifier(repo, doc, classifier_name, classifier, meta):
    num_changed = 0

    examine_part = classifier["acts_on"]

    for githash in doc.get_hashes():
        entry = doc.get_entry(githash)
        # Skip if we already have an automatic class
        if entry.has_auto_cat():
            continue

        gitcommit = repo.get_commit(githash)

        if examine_part == "message":
            examine = gitcommit.message
        elif examine_part == "summary":
            examine = gitcommit.summary
        elif examine_part == "filenames":
            examine = gitcommit.modified_files
        else:
            raise NotImplementedError

        # Special-case
        if classifier_name == "00-reverts":
            num_changed += apply_revert(
                repo, doc, classifier_name, classifier, githash, examine
            )
            continue

        # Handle filenames differently
        if examine_part == "filenames":
            for pattern, cat in classifier.items():
                if not all([re.search(pattern, f) for f in examine]):
                    continue
                entry.set_auto_cat(cat, classifier_name, pattern)
                num_changed += 1
            if entry.has_auto_cat():
                continue

            # Try omitting the specified files
            new_examine = [
                f
                for f in examine
                if not any(
                    re.search(omit_pattern, f)
                    for omit_pattern in meta["filenames_try_omit"]
                )
            ]
            if len(new_examine) == 0:
                continue
            if new_examine == examine:
                continue
            examine = new_examine

            for pattern, cat in classifier.items():
                if not all([re.search(pattern, f) for f in examine]):
                    continue
                entry.set_auto_cat(cat, classifier_name, pattern)
                num_changed += 1

            continue

        # Handle texts (summary or message)
        for pattern, cat in classifier.items():
            match = re.search(pattern, examine)
            if not match:
                continue

            entry.set_auto_cat(cat, classifier_name, pattern)
            num_changed += 1

    if num_changed > 0:
        print(f"Classified {num_changed} commits due to {classifier_name}")


def group_commits(repo, doc):
    """Find and group consecutive commits with the same author, category, and
    commit summary prefix.
    """
    # Look for commits that we can group together:
    adjacents = [[None, 0, None, None]]
    for githash, entry in doc.get_entries():
        gitcommit = repo.get_commit(githash)
        # Extract relevant info
        prefix = commits_periodical.utils.get_summary_prefix(gitcommit)
        cat = entry.cat
        author = str(gitcommit.author).replace(" ", "_")

        # Combine info
        combo = (author, cat, prefix)
        prev = adjacents[-1]
        if prev[0] == combo:
            prev[1] += 1
            prev[2].append(githash)
            prev[3].append(gitcommit)
        else:
            adjacents.append([combo, 1, [githash], [gitcommit]])
    # Remove the "None" first item
    adjacents.pop(0)

    # Split into veryshrot + adjacent
    combos = []
    for adj in adjacents:
        if len(adj[3]) < GROUP_AT_LEAST:
            continue

        adjcombos = collections.defaultdict(list)
        for githash, gitcommit in zip(adj[2], adj[3]):
            author = adj[0]
            prefix = commits_periodical.utils.get_summary_prefix(gitcommit)
            combo = (prefix, author)
            adjcombos[combo].append((githash, gitcommit))

        for key, value in adjcombos.items():
            if len(value) < GROUP_AT_LEAST:
                continue
            combos.append((key, value))

    for combo, values in combos:
        githashes = [s[0] for s in values]
        prefix, author = combo

        # Do we already have a group?
        has_group = None
        for githash in githashes:
            entry = doc.entries[githash]
            if entry.has_group():
                has_group = entry.groupname()
                break

        if has_group:
            doc.set_group(githashes, prefix, has_group)
        else:
            doc.set_group(githashes, prefix)


def classify_period(repo, doc, project):
    doc.clear_automatic_annotations()

    for name, classifier in project.classifiers.items():
        apply_classifier(repo, doc, name, classifier, project.meta)

    # group
    group_commits(repo, doc)

    # highlighted
    find_highlighted(repo, doc)

    doc.save()
