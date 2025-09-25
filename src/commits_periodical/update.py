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
