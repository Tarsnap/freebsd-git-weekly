def investigate(repo, doc, funcs):
    print(f"Investigating {len(doc.entries)} commits")

    for func in funcs:
        match func:
            case _:
                print(f"Function name not recognized: {func}")
                exit(1)
