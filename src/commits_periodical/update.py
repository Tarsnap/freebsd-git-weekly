def update_ref(repo, metadata_file, metadata):
    # Get the HEAD from git, and the latest in the metadata
    latest_hash = repo.get_head_hash()

    if "end_including" not in metadata:
        return

    # If it's different, replace the final hash
    if metadata["end_including"] != latest_hash:
        metadata["end_including"] = latest_hash
        metadata_file.save()


def get_new_hashes(repo, metadata, doc):
    """Get any new hashes in the range specified in metadata that are not
    already in the summary file.
    """
    start_after = metadata["start_after"]
    end_including = metadata["end_including"]
    repo.ensure_cached(start_after, end_including)
    githashes = repo.get_githashes()
    existing_hashes = doc.get_hashes()

    new_hashes = [h for h in githashes if h not in existing_hashes]
    return new_hashes


def update_period(repo, metadata, doc):
    """Update the latest week."""
    print(f"Updating {doc.filename}")

    new_hashes = get_new_hashes(repo, metadata, doc)

    if not new_hashes:
        print("No new commits within range")
        return

    num_added = 0
    for githash in new_hashes:
        doc.add_commit(githash)
        num_added += 1

    doc.save()

    print(f"Added {num_added} commits")
