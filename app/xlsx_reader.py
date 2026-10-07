"""Leitura enxuta de planilhas .xlsx usando somente a biblioteca padrão."""

from __future__ import annotations

from io import BytesIO
from typing import Iterator
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"main": MAIN_NS, "r": DOC_REL_NS, "rel": PKG_REL_NS}


class SpreadsheetError(ValueError):
    """Planilha inválida ou fora do formato suportado."""


def _column_number(cell_reference: str) -> int:
    letters = "".join(char for char in cell_reference if char.isalpha()).upper()
    number = 0
    for char in letters:
        number = number * 26 + ord(char) - 64
    return number


def _shared_strings(book: ZipFile) -> list[str]:
    try:
        stream = book.open("xl/sharedStrings.xml")
    except KeyError:
        return []
    strings: list[str] = []
    with stream:
        for _, element in ET.iterparse(stream, events=("end",)):
            if element.tag == f"{{{MAIN_NS}}}si":
                strings.append("".join(node.text or "" for node in element.iter(f"{{{MAIN_NS}}}t")))
                element.clear()
    return strings


def _first_sheet_path(book: ZipFile) -> str:
    try:
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        first_sheet = workbook.find("main:sheets/main:sheet", NS)
        if first_sheet is None:
            raise SpreadsheetError("A pasta de trabalho não possui abas.")
        relation_id = first_sheet.attrib.get(f"{{{DOC_REL_NS}}}id")
        relations = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        for relation in relations.findall("rel:Relationship", NS):
            if relation.attrib.get("Id") == relation_id:
                target = relation.attrib.get("Target", "")
                if target.startswith("/"):
                    return target.lstrip("/")
                return "xl/" + target.lstrip("/")
    except KeyError as exc:
        raise SpreadsheetError("O arquivo não parece ser uma planilha .xlsx válida.") from exc
    raise SpreadsheetError("Não foi possível localizar a primeira aba da planilha.")


def iter_first_sheet(data: bytes) -> Iterator[list[str]]:
    """Produz as linhas da primeira aba da planilha, preservando células vazias."""
    try:
        book = ZipFile(BytesIO(data))
    except BadZipFile as exc:
        raise SpreadsheetError("O arquivo enviado não é um Excel .xlsx válido.") from exc

    with book:
        shared = _shared_strings(book)
        sheet_path = _first_sheet_path(book)
        try:
            stream = book.open(sheet_path)
        except KeyError as exc:
            raise SpreadsheetError("Não foi possível abrir a primeira aba da planilha.") from exc

        with stream:
            for _, row in ET.iterparse(stream, events=("end",)):
                if row.tag != f"{{{MAIN_NS}}}row":
                    continue
                values: list[str] = []
                for cell in row.findall("main:c", NS):
                    column = _column_number(cell.attrib.get("r", "A1"))
                    while len(values) < column:
                        values.append("")
                    value_node = cell.find("main:v", NS)
                    value = value_node.text if value_node is not None and value_node.text else ""
                    cell_type = cell.attrib.get("t")
                    if cell_type == "s" and value:
                        try:
                            value = shared[int(value)]
                        except (ValueError, IndexError):
                            value = ""
                    elif cell_type == "inlineStr":
                        inline = cell.find("main:is", NS)
                        value = "".join(node.text or "" for node in inline.iter(f"{{{MAIN_NS}}}t")) if inline is not None else ""
                    while len(values) >= column:
                        values[column - 1] = str(value).strip()
                        break
                row.clear()
                if any(values):
                    yield values
