from __future__ import annotations

import posixpath
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CELL_REFERENCE = re.compile(r"(?P<column>[A-Z]+)\d+")


def _column_index(reference: str) -> int:
    match = CELL_REFERENCE.fullmatch(reference.upper())
    if not match:
        raise ValueError(f"invalid XLSX cell reference: {reference}")
    index = 0
    for character in match.group("column"):
        index = index * 26 + ord(character) - ord("A") + 1
    return index - 1


def _text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return "".join(node.text or "" for node in element.iter(f"{{{MAIN_NS}}}t"))


def _shared_strings(archive: ZipFile) -> tuple[str, ...]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return ()
    return tuple(_text(item) for item in root.findall(f"{{{MAIN_NS}}}si"))


def _first_sheet_path(archive: ZipFile) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    first_sheet = workbook.find(f".//{{{MAIN_NS}}}sheet")
    if first_sheet is None:
        raise ValueError("XLSX workbook does not contain a worksheet")
    relationship_id = first_sheet.attrib.get(f"{{{REL_NS}}}id")
    if not relationship_id:
        raise ValueError("XLSX worksheet is missing its relationship ID")

    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    for relationship in relationships.findall(f"{{{PACKAGE_REL_NS}}}Relationship"):
        if relationship.attrib.get("Id") != relationship_id:
            continue
        target = relationship.attrib.get("Target", "")
        if target.startswith("/"):
            return target.lstrip("/")
        return posixpath.normpath(posixpath.join("xl", target))
    raise ValueError("XLSX worksheet relationship could not be resolved")


def _cell_value(cell: ET.Element, shared_strings: tuple[str, ...]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return _text(cell.find(f"{{{MAIN_NS}}}is"))

    value_node = cell.find(f"{{{MAIN_NS}}}v")
    value = "" if value_node is None else value_node.text or ""
    if cell_type == "s" and value:
        index = int(value)
        if index >= len(shared_strings):
            raise ValueError(f"XLSX shared-string index is out of range: {index}")
        return shared_strings[index]
    if cell_type == "b":
        return "TRUE" if value == "1" else "FALSE"
    return value


def read_first_worksheet(path: str | Path) -> list[dict[str, str]]:
    """Read a simple directory table from the first worksheet using the standard library."""

    with ZipFile(path) as archive:
        shared_strings = _shared_strings(archive)
        sheet = ET.fromstring(archive.read(_first_sheet_path(archive)))

    matrix: list[list[str]] = []
    for row in sheet.findall(f".//{{{MAIN_NS}}}sheetData/{{{MAIN_NS}}}row"):
        values: list[str] = []
        for cell in row.findall(f"{{{MAIN_NS}}}c"):
            reference = cell.attrib.get("r", "")
            column_index = _column_index(reference)
            if len(values) <= column_index:
                values.extend("" for _ in range(column_index + 1 - len(values)))
            values[column_index] = _cell_value(cell, shared_strings)
        matrix.append(values)

    if not matrix:
        return []
    headers = [value.strip() for value in matrix[0]]
    records: list[dict[str, str]] = []
    for values in matrix[1:]:
        if not any(value.strip() for value in values):
            continue
        records.append(
            {
                header: values[index] if index < len(values) else ""
                for index, header in enumerate(headers)
                if header
            }
        )
    return records
