def check_disputed(repo, doc):
    num_disputed = 0
    print("Disputed entries:")
    for githash, entry in doc.get_entries():
        if not entry.is_cat_disputed():
            continue
        if not entry.has_auto_cat():
            continue
        print(entry)
        print()
        num_disputed += 1

    if num_disputed == 0:
        print("  (No disputed entries in this report)")


def investigate(repo, doc, funcs):
    print(f"Investigating {len(doc.entries)} commits")

    for func in funcs:
        match func:
            case "disputed":
                check_disputed(repo, doc)
            case _:
                print(f"Function name not recognized: {func}")
                exit(1)
