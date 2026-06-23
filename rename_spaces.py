#!/usr/bin/env python3
"""
Rename all files and directories in the current directory (recursively)
that contain spaces in their names to use underscores instead.
"""

import os
import sys


def rename_files_with_spaces(root_dir=None):
    if root_dir is None:
        root_dir = os.getcwd()

    # top_down=False processes deepest subdirectories first.
    # This prevents parent directory renames from breaking child paths.
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        # 1. Rename files first
        for filename in filenames:
            if " " in filename:
                new_filename = filename.replace(" ", "_")
                src_file = os.path.join(dirpath, filename)
                dst_file = os.path.join(dirpath, new_filename)

                if os.path.exists(dst_file):
                    print(f"Skipping: {src_file} -> target exists", file=sys.stderr)
                    continue

                os.rename(src_file, dst_file)
                print(f"Renamed File: {src_file} -> {dst_file}")

        # 2. Rename directories safely
        for dirname in dirnames:
            if " " in dirname:
                new_dirname = dirname.replace(" ", "_")
                src_dir = os.path.join(dirpath, dirname)
                dst_dir = os.path.join(dirpath, new_dirname)

                if os.path.exists(dst_dir):
                    print(f"Skipping: {src_dir} -> target exists", file=sys.stderr)
                    continue

                os.rename(src_dir, dst_dir)
                print(f"Renamed Dir:  {src_dir} -> {dst_dir}")


if __name__ == "__main__":
    rename_files_with_spaces()
