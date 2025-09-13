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
        "--start-date",
        type=str,
        default="",
        help="Beginning of the time period to examine",
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
    metadata_file = commits_periodical.data.MetadataFile(project_dirname)

    # Get the relevant time period
    if not args.start_date:
        # Default setting: use the most recent time period
        datestr = metadata_file.get_latest_datestr()
        entries_filename = metadata_file.get_latest_filename()
    else:
        datestr = args.start_date
        entries_filename = os.path.join(project_dirname, f"{datestr}.toml")

    metadata = metadata_file.get_metadata(datestr)
    cache_filename = entries_filename.replace(".toml", ".gitcache")
    repo = commits_periodical.gitlayer.CachedRepo(
        config["git_dir"], cache_filename
    )
    doc = commits_periodical.data.Week(entries_filename)
    project = commits_periodical.project_data.ProjectData(project_dirname)

    # Run the relevant command
    match args.command:
        case "sanity":
            commits_periodical.sanity_check.check(project)
        case "update":
            commits_periodical.update.update_ref(repo, metadata_file, metadata)
            commits_periodical.update.update_period(repo, metadata, doc)
        case "update-commits":
            commits_periodical.update.update_period(repo, metadata, doc)
        case "annotate":
            commits_periodical.classify.classify_period(repo, doc, project)
        case "generate":
            commits_periodical.generate.generate_index(metadata_file)
            commits_periodical.generate.generate_period(
                repo, doc, project, metadata, args.debug
            )
        case _:
            print(f"Command not recognized: {args.command}")


if __name__ == "__main__":
    main()
