import sys


def sanity_check_files_categories(texts):
    """Conflicting filenames in 'plain' filenames section."""
    st = sorted(texts)
    for prev, after in zip(st[:-1], st[1:]):
        if after.startswith(prev):
            msg = f"Conflicting filename patterns found:\n  {prev}\n  {after}"
            raise Exception(msg)


def check_section(order, section, section_name):
    """Does this section contain keys in the correct order?"""
    section_keys = list(section.keys())

    for category in section_keys:
        if category not in order:
            print(f"Incorrect category: {category}")
            return False

    sorted_section_keys = sorted(section_keys, key=order.get)

    if section_keys != sorted_section_keys:
        print(f"Incorrect order in {section}:")
        print(f"{section_keys}\n{sorted_section_keys}")
        return False

    return True


def check(project):
    order = {key: i for i, key in enumerate(project.categories)}

    for section in project.classifiers:
        if section == "Meta":
            continue

        if "filenames_plain" in section:
            sanity_check_files_categories(project.classifiers[section].keys())

        if not check_section(order, project.orig_classifiers[section], section):
            print("Problem found")
            sys.exit(1)
