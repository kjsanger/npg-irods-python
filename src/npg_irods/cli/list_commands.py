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
from collections.abc import Iterable
from importlib import import_module, metadata

from npg_irods import version

description = """
List installed npg-irods command entrypoints.
"""

no_description = "(no description available)"


def command_entry_points(
    entry_points: Iterable[metadata.EntryPoint],
) -> list[metadata.EntryPoint]:
    """Return sorted npg_irods.cli console entrypoints."""
    filtered = []

    for entry_point in entry_points:
        module = entry_point.value.split(":", maxsplit=1)[0]
        if entry_point.group == "console_scripts" and (
            module == "npg_irods.cli" or module.startswith("npg_irods.cli.")
        ):
            filtered.append(entry_point)

    return sorted(filtered, key=lambda ep: ep.name)


def command_names(
    entry_points: Iterable[metadata.EntryPoint],
) -> list[str]:
    """Return sorted command names for npg_irods.cli entrypoints."""
    return [entry_point.name for entry_point in command_entry_points(entry_points)]


def description_for_module(module_name: str) -> str:
    """Return the first paragraph of a module's description as a single line."""
    try:
        module = import_module(module_name)
    except ImportError:
        return no_description

    value = getattr(module, "description", None)
    if not isinstance(value, str):
        return no_description

    return first_paragraph(value)


def first_paragraph(text: str) -> str:
    """Return the first paragraph of text as a single line."""
    text = text.strip()
    if not text:
        return no_description

    desc_lines = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            desc_lines.append(line)
        else:
            break

    return " ".join(desc_lines)


def list_commands() -> list[tuple[str, str]]:
    """Return a list of console script command names and their descriptions."""
    entrypoints = metadata.entry_points(group="console_scripts")

    commands = []
    for entry_point in command_entry_points(entrypoints):
        module_name = entry_point.value.split(":", maxsplit=1)[0]
        commands.append((entry_point.name, description_for_module(module_name)))

    return commands


def main(argv=None):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--version",
        help="Print the version and exit.",
        action="version",
        version=version(),
    )
    parser.parse_args(argv)

    for name, command_description in list_commands():
        print(f"{name}\t{command_description}")
