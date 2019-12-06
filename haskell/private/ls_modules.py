#!/usr/bin/env python3
#
# Create a list of exposed modules (including reexported modules)
# given a directory full of interface files and the content of the
# global package database (to mine the versions of all prebuilt
# dependencies). The exposed modules are filtered using a provided
# list of hidden modules, and augmented with reexport declarations.

from __future__ import unicode_literals, print_function

import collections
import fnmatch
import itertools
import os
import re
import sys
import io

if len(sys.argv) != 7:
    sys.exit("Usage: %s <WITH_PROFILING> <DIRECTORY> <GLOBAL_PKG_DB> <HIDDEN_MODS_FILE> <REEXPORTED_MODS_FILE> <RESULT_FILE>" % sys.argv[0])

with_profiling = sys.argv[1] == 'True'
root = sys.argv[2]
global_pkg_db_dump = sys.argv[3]
hidden_modules_file = sys.argv[4]
reexported_modules_file = sys.argv[5]
results_file = sys.argv[6]

def read_config_file(f):
    """
    Read GHC package database format, which is mostly key:values lines

    `f` is an open file descriptor
    it returns a generator of (key, [values])
    """

    current_field_name = None
    current_field_values = []


    # we parse the file line by line, looking for "fieldName:" markers
    # and then consuming all the following line if they are indented.
    for line in f:
        # we have an indented line, that's a field
        if line.startswith("    "):
            line = line.strip()
            if line:
                current_field_values.append(line.strip())
        else:
            # Dump the currently read field
            if current_field_name:
                yield (current_field_name, current_field_values)

            # this is a new field
            if ':' in line:
               items = line.split(':')
               current_field_name = items[0].strip()

               if len(items) == 2:
                   maybefield = items[1].strip()

                   if maybefield:
                       current_field_values = [maybefield]
                   else:
                       current_field_values = []
            else:
                current_field_name = None
                current_field_values = []

with io.open(global_pkg_db_dump, "r", encoding='utf8') as f:
    names = []
    ids = []

    # read names and ids entries from the database
    for (field, values) in read_config_file(f):
        if field == "name" and len(values) == 1:
            names.append(values[0])
        if field == "id" and len(values) == 1:
            ids.append(values[0])

    names.sort()
    ids.sort()

    # A few sanity checks.
    assert len(names) == len(ids)

    # compute duplicate, i.e. package name associated with multiples ids
    duplicates = set()
    if len(names) != len(set(names)):
        duplicates = set([
            name for name, count in collections.Counter(names).items()
            if count > 1
        ])

    # This associate pkg name to pkg id
    pkg_ids_map = dict(zip(names, ids))

with io.open(hidden_modules_file, "r", encoding='utf8') as f:
    hidden_modules = [mod.strip() for mod in f.read().split(",")]

with io.open(reexported_modules_file, "r", encoding='utf8') as f:
    raw_reexported_modules = (
        mod.strip() for mod in f.read().split(",") if mod.strip()
    )
    # Substitute package ids for package names in reexports, because
    # GHC really wants package ids.
    regexp = re.compile("from (%s):" % "|".join(map(re.escape, pkg_ids_map)))

    def replace_pkg_by_pkgid(match):
        pkgname = match.group(1)

        if pkgname in duplicates:
            sys.exit(
                "\n".join([
                    "Multiple versions of the following packages installed: ",
                    ", ".join(duplicates),
                    "\nThe following was explictly used: " + pkgname,
                    "\nThis is not currently supported.",
                ])
            )

        return "from %s:" % pkg_ids_map[pkgname]

    reexported_modules = (
        regexp.sub(replace_pkg_by_pkgid, mod)
        for mod in raw_reexported_modules
    )

def handle_walk_error(e):
    print("""
Failed to list interface files:
    {}
On Windows you may need to enable long file path support:
    Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name 'LongPathsEnabled' -Value 1
    """.strip().format(e), file=sys.stderr)
    exit(1)

interface_files = (
    os.path.join(path, f)
    for path, dirs, files in os.walk(root, onerror=handle_walk_error)
    for f in fnmatch.filter(files, '*.p_hi' if with_profiling else '*.hi')
)

modules = (
    # replace directory separators by . to generate module names
    # / and \ are respectively the separators for unix (linux / darwin) and windows systems
    os.path.splitext(os.path.relpath(f, start=root))[0]
        .replace("/",".")
        .replace("\\",".")
    for f in interface_files
)

exposed_modules = (
    m
    for m in modules
    if m not in hidden_modules
)

with io.open(results_file, "w", encoding='utf8') as f:
    f.write(", ".join(itertools.chain(exposed_modules, reexported_modules)))
