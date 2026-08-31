class SanityCheckError(Exception):
    pass


def sanity_check_files_categories(texts):
    """Check for conflicting filenames in 'plain' filenames section."""
    st = sorted(texts)
    for prev, after in zip(st[:-1], st[1:]):
        if after.startswith(prev):
            msg = f"Conflicting filename patterns found:\n  {prev}\n  {after}"
            raise SanityCheckError(msg)


def check_section(order, section, section_name):
    """Check that this section contains keys in the correct order."""
    section_keys = list(section.keys())

    for category in section_keys:
        if category not in order:
            msg = f"Incorrect category: {category}"
            raise SanityCheckError(msg)

    sorted_section_keys = sorted(section_keys, key=order.get)

    if section_keys != sorted_section_keys:
        msg = f"Incorrect order in {section_name}: "
        msg += f"{section_keys}\n{sorted_section_keys}"
        raise SanityCheckError(msg)


def check(project):
    order = {key: i for i, key in enumerate(project.categories)}
    order["_acts_on"] = -2
    order["_re_func"] = -1

    for section in project.classifiers:
        if section == "Meta":
            continue

        if "filenames_plain" in section:
            patterns = []
            for _, pats in project.classifiers[section].rules.items():
                patterns.extend(pats)
            sanity_check_files_categories(patterns)

        check_section(order, project.orig_classifiers[section], section)
