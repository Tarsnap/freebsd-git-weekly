#!/usr/bin/env python3

import argparse
import os
import sys

import commits_periodical.classify
import commits_periodical.generate
import commits_periodical.project_data
import commits_periodical.sanity_check
import commits_periodical.update
import commits_periodical.utils


def parse_args():
    """Parse the command-line arguments."""
    parser = argparse.ArgumentParser(
        description="FreeBSD git weekly classification"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print debugging info to console and in HTML",
    )
    parser.add_argument(
        "-r",
        "--report",
        type=str,
        default="",
        help="Name of the report to act on",
    )
    parser.add_argument(
        "--reproducible",
        action="store_true",
        default=False,
        help="Don't include the current time in the footer",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("sanity", help="Sanity check")
    subparsers.add_parser("update", help="Update the final ref and commits")
    subparsers.add_parser("update-commits", help="Update the commits only")
    subparsers.add_parser("annotate", help="Annotate a week's git commits")
    subparsers.add_parser("generate", help="Generate html for a week")
    args = parser.parse_args()
    return args


def get_config():
    # Get the filename
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if not xdg_config:
        # Use default
        xdg_config = os.path.join(os.path.expanduser("~"), ".config")
    config_filename = os.path.join(
        xdg_config, "freebsd-git-weekly", "freebsd-git-weekly.conf"
    )

    # Check that it exists
    if not os.path.exists(config_filename):
        print(f"Config file required, please create:\n  {config_filename}")
        sys.exit(1)

    # Read it
    config = commits_periodical.utils.read_toml(config_filename)
    return config


def main():
    """FreeBSD weekly commit summaries."""
    args = parse_args()

    config = get_config()
    project_dirname = os.path.expanduser(config["project_dir"])
    if args.command == "update":
        index = commits_periodical.data.Index(project_dirname, read_only=False)
    else:
        index = commits_periodical.data.Index(project_dirname)

    # Get the relevant time period
    if not args.report:
        # Default setting: use the most recent time period
        report_name = index.get_latest_name()
        entries_filename = index.get_latest_filename()
    else:
        report_name = args.report
        entries_filename = os.path.join(project_dirname, f"{report_name}.toml")

    report = index.get_report(report_name)
    cache_filename = entries_filename.replace(".toml", ".gitcache")
    repo = commits_periodical.gitlayer.CachedRepo(
        config["git_dir"], cache_filename
    )
    if report.is_derived():
        doc = commits_periodical.data.Week(None)
    else:
        if args.command == "update" or args.command == "annotate":
            doc = commits_periodical.data.Week(
                entries_filename, read_only=False
            )
        else:
            doc = commits_periodical.data.Week(entries_filename)
    project = commits_periodical.project_data.ProjectData(project_dirname)

    # Run the relevant command
    match args.command:
        case "sanity":
            commits_periodical.sanity_check.check(project)
        case "update":
            if report.is_ongoing():
                commits_periodical.update.update_ref(repo, index, report)
            commits_periodical.update.update_period(repo, report, doc)
        case "update-commits":
            commits_periodical.update.update_period(repo, report, doc)
        case "annotate":
            if not report.is_derived():
                commits_periodical.classify.classify_period(repo, doc, project)
        case "generate":
            commits_periodical.generate.generate_index(project_dirname, index)
            commits_periodical.generate.generate_period(
                repo,
                doc,
                project,
                report,
                args.debug,
                project_dirname,
                args.reproducible,
                report_name,
            )
        case _:
            print(f"Command not recognized: {args.command}")


if __name__ == "__main__":
    main()
