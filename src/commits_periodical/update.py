import datetime


def update_ref(repo, index, index_entry):
    if index_entry.is_derived():
        return

    # Get the HEAD from git, and the latest in the index_entry
    latest_hash = repo.get_head_hash()

    # If it's different, replace the final hash
    if index_entry["end_including"] != latest_hash:
        index_entry.set_end_including(latest_hash)
        index.save()


def get_new_hashes(repo, index_entry, doc):
    """Get any new hashes in the range specified in index_entry that are not
    already in the summary file.
    """
    start_after = index_entry["start_after"]
    end_including = index_entry["end_including"]
    repo.ensure_cached(start_after, end_including)
    githashes = repo.get_githashes()
    existing_hashes = doc.get_hashes()

    new_hashes = [h for h in githashes if h not in existing_hashes]
    return new_hashes


def update_period(repo, index_entry, doc):
    """Update the latest report."""
    if index_entry.is_derived():
        return

    print(f"Updating {doc.filename}")

    new_hashes = get_new_hashes(repo, index_entry, doc)

    if not new_hashes:
        print("No new commits within range")
        return

    num_added = 0
    for githash in new_hashes:
        doc.add_commit(githash)
        num_added += 1

    doc.save()

    print(f"Added {num_added} commits")


def _add_week(date_str):
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    dt = dt + datetime.timedelta(days=7)
    return dt.strftime("%Y-%m-%d")


def new_report(index, index_entry, githash):
    # Update the ref in the latest index entry
    index_entry.set_end_including(githash)
    index_entry.remove_ongoing()

    # Make a new index entry
    previous_name = index.get_latest_name()
    report_name = _add_week(previous_name)
    date_start = _add_week(index_entry.get("display_date_start"))
    date_end = _add_week(index_entry.get("display_date_end"))
    new_index_entry_data = {
        "display_date_start": date_start,
        "display_date_end": date_end,
        "start_after": githash,
        "end_including": githash,
        "ongoing": True,
    }
    index.add_index_entry_after(
        report_name, new_index_entry_data, previous_name
    )

    # We're finished
    index.save()
