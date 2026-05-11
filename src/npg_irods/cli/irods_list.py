# -*- coding: utf-8 -*-
#
# Copyright © 2026 Genome Research Ltd. All rights reserved.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import argparse
import csv
import sys
from pathlib import PurePath

import structlog
from npg.cli import add_logging_arguments
from npg.log import configure_structlog
from partisan.irods import Collection, DataObject, make_rods_item

from npg_irods import add_appinfo_structlog_processor, version

description = """
A utility for listing iRODS data objects and collections, optionally including metadata
and permission information, with output in JSON or tab-delimited formats.

For tab-delimited output, the output columns are:

    Column 0: Full path
    Column 1: iRODS path type ("coll" or "obj")
    Column 2: Size in bytes for data objects (empty for collections)
    Column 3: Checksum string for data objects (empty for collections)
    Column 4: Metadata type ("acl" or "avu")
    Column 5: Metadata attribute
    Column 6: Metadata value

Tab-delimited output for a given path will include one row per tuple of metadata and/or
ACL information, so there may be multiple rows. Columns that are not available e.g.
"checksum" and "size" for collections, are populated with empty strings to keep the
table rectangular.

JSON output is not configurable with the --acl, --avu, or --size options; the full JSON
representation will be printed.
"""


OBJ_LABEL = "obj"
COLL_LABEL = "coll"
ACL_LABEL = "acl"
AVU_LABEL = "avu"


def logger():
    return structlog.get_logger("main")


def _print_item_rows(writer, item, acl, avu, size, checksum):
    """Print details of a RodsItem.

    Column 0: Full path
    Column 1: iRODS path type ("coll" or "obj")
    Column 2: Size in bytes for data objects
    Column 3: Checksum for data objects
    Column 4: Metadata type ("acl", "avu")
    Column 5: Metadata attribute
    Column 6: Metadata value
    """
    try:
        p = str(item)
        t = COLL_LABEL if item.rods_type == Collection else OBJ_LABEL
        s = item.size() if item.rods_type == DataObject and size else ""
        c = item.checksum() if item.rods_type == DataObject and checksum else ""

        rows = []
        if not acl and not avu:
            rows.append([p, t, s, c, "", "", ""])
        else:
            if acl:
                for ac in item.acl():
                    rows.append(
                        [p, t, s, c, ACL_LABEL, f"{ac.user}#{ac.zone}", ac.perm.value]
                    )
            if avu:
                for av in item.metadata():
                    rows.append([p, t, s, c, AVU_LABEL, av.attribute, av.value])

        writer.writerows(rows)
    except Exception as e:
        logger().error(f"Error printing {item}: {e}")


def _print_item_json(item, *_):
    try:
        print(item.to_json(), end="\n")
    except Exception as e:
        logger().error(f"Error printing {item}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Note: --json cannot be combined with --acl, --avu, --size, or --checksum.",
    )
    add_logging_arguments(parser)
    parser.add_argument("paths", type=str, nargs="+")

    type_group = parser.add_mutually_exclusive_group()
    type_group.add_argument(
        "--obj", help="Include data object details in output.", action="store_true"
    )
    type_group.add_argument(
        "--coll", help="Include collection details in output.", action="store_true"
    )

    parser.add_argument("--acl", help="Include ACL in output.", action="store_true")
    parser.add_argument("--avu", help="Include AVUs in output.", action="store_true")
    parser.add_argument(
        "--checksum", help="Print the checksum of data objects.", action="store_true"
    )
    parser.add_argument(
        "--size", help="Print the size of data objects in bytes.", action="store_true"
    )
    parser.add_argument("--json", help="Output in JSON format.", action="store_true")
    parser.add_argument(
        "--recurse", help="Recurse into collections when listing.", action="store_true"
    )
    parser.add_argument(
        "--version",
        help="Print the version and exit.",
        action="version",
        version=version(),
    )

    args = parser.parse_args()
    configure_structlog(
        config_file=args.log_config,
        debug=args.debug,
        verbose=args.verbose,
        colour=args.colour,
        json=args.log_json,
    )
    add_appinfo_structlog_processor()

    obj = args.obj
    coll = args.coll
    avu = args.avu
    acl = args.acl
    size = args.size
    checksum = args.checksum
    recurse = args.recurse

    if args.json and (args.acl or args.avu or args.size or args.checksum):
        parser.error("--json cannot be used with --acl, --avu, --size, or --checksum")

    if not obj and not coll:  # Default to printing both if neither is selected
        obj = True
        coll = True

    if args.json:
        _print_item = _print_item_json
    else:
        writer = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
        _print_item = lambda x, *_args: _print_item_rows(writer, x, *_args)

    for path in args.paths:
        p = PurePath(path)
        if not p.is_absolute():
            logger().error("Path must be absolute; skipping", path=p.as_posix())

        item = make_rods_item(p)
        if not item.exists():
            logger().warn("Path does not exist; skipping", path=p.as_posix())
            continue

        if item.rods_type == DataObject and obj:
            _print_item(item, acl, avu, size, checksum)
        elif item.rods_type == Collection:
            if coll:
                _print_item(item, acl, avu, size, checksum)

            for x in item.iter_contents(avu=avu, acl=acl, recurse=recurse):
                if x.rods_type == DataObject and obj:
                    _print_item(x, acl, avu, size, checksum)
                elif x.rods_type == Collection and coll:
                    _print_item(x, acl, avu, size, checksum)
