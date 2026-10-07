"""Importação e consulta dos dados PCASP no banco local."""

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path

from app.config import DATABASE_PATH, DATA_DIR
from app.xlsx_reader import SpreadsheetError, iter_first_sheet


def _key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char)).strip()


def _column(headers: list[str], wanted: str, *, last: bool = False) -> int | None:
    matches = [index for index, name in enumerate(headers) if _key(name) == _key(wanted)]
    if not matches:
        return None
    return matches[-1] if last else matches[0]


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS accounts (
            code TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            function TEXT NOT NULL DEFAULT '',
            balance_nature TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT '',
            details TEXT NOT NULL DEFAULT '',
            source_row TEXT NOT NULL DEFAULT ''
        )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS metadata (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )"""
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_accounts_status ON accounts(status)")


def import_workbook(data: bytes, filename: str) -> int:
    rows = iter_first_sheet(data)
    try:
        headers = next(rows)
    except StopIteration as exc:
        raise SpreadsheetError("A primeira aba está vazia.") from exc

    code_i = _column(headers, "CONTA")
    title_i = _column(headers, "TÍTULO", last=True)
    function_i = _column(headers, "FUNÇÃO")
    nature_i = _column(headers, "NATUREZA DO SALDO")
    status_i = _column(headers, "STATUS")
    if code_i is None or title_i is None:
        raise SpreadsheetError("Não encontrei as colunas obrigatórias CONTA e TÍTULO na primeira aba.")
    if function_i is None:
        raise SpreadsheetError("Não encontrei a coluna FUNÇÃO na primeira aba.")

    def at(values: list[str], index: int | None) -> str:
        return values[index].strip() if index is not None and index < len(values) else ""

    connection = connect()
    inserted = 0
    try:
        _schema(connection)
        with connection:
            connection.execute("DELETE FROM accounts")
            for values in rows:
                code = at(values, code_i)
                title = at(values, title_i)
                if not code or not title:
                    continue
                details = []
                for index, header in enumerate(headers):
                    label = header.strip() if header else ""
                    value = at(values, index)
                    if label and value and index not in {code_i, title_i, function_i, nature_i, status_i}:
                        details.append(f"{label}: {value}")
                connection.execute(
                    """INSERT OR REPLACE INTO accounts
                       (code, title, function, balance_nature, status, details, source_row)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (code, title, at(values, function_i), at(values, nature_i), at(values, status_i),
                     "\n".join(details), json.dumps(values, ensure_ascii=False)),
                )
                inserted += 1
            if inserted == 0:
                raise SpreadsheetError("Não encontrei contas válidas para importar.")
            now = datetime.now().astimezone().isoformat(timespec="seconds")
            connection.execute(
                "INSERT OR REPLACE INTO metadata(name, value) VALUES('source', ?)",
                (Path(filename).name,),
            )
            connection.execute(
                "INSERT OR REPLACE INTO metadata(name, value) VALUES('updated_at', ?)",
                (now,),
            )
            connection.execute(
                "INSERT OR REPLACE INTO metadata(name, value) VALUES('account_count', ?)",
                (str(inserted),),
            )
    finally:
        connection.close()
    return inserted


def ensure_initial_data(workbook_path: Path) -> None:
    connection = connect()
    try:
        _schema(connection)
        count = connection.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    finally:
        connection.close()
    if count == 0 and workbook_path.exists():
        import_workbook(workbook_path.read_bytes(), workbook_path.name)


def get_status() -> dict[str, str | int]:
    connection = connect()
    try:
        _schema(connection)
        count = connection.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        metadata = {row["name"]: row["value"] for row in connection.execute("SELECT name, value FROM metadata")}
        return {
            "account_count": count,
            "source": metadata.get("source", "Nenhuma planilha importada"),
            "updated_at": metadata.get("updated_at", ""),
        }
    finally:
        connection.close()


def search_accounts(query: str, kind: str = "") -> list[dict[str, str | int]]:
    connection = connect()
    try:
        records = connection.execute(
            "SELECT code, title, function, balance_nature, status, details FROM accounts"
        ).fetchall()
    finally:
        connection.close()

    stopwords = {"com", "das", "dos", "de", "da", "do", "em", "para", "por", "um", "uma"}
    aliases = {
        "computador": ("equipamento", "processamento", "dados"),
        "notebook": ("equipamento", "processamento", "dados"),
        "laptop": ("equipamento", "processamento", "dados"),
        "desktop": ("equipamento", "processamento", "dados"),
        "impressora": ("equipamento", "processamento", "dados"),
        "cadeira": ("mobiliario", "moveis"),
        "mesa": ("mobiliario", "moveis"),
        "armario": ("mobiliario", "moveis"),
        "estante": ("mobiliario", "moveis"),
        "geladeira": ("aparelhos", "utensilios", "domesticos"),
        "frigobar": ("aparelhos", "utensilios", "domesticos"),
        "fogao": ("aparelhos", "utensilios", "domesticos"),
        "carro": ("veiculos",),
        "automovel": ("veiculos",),
        "caminhonete": ("veiculos",),
        "moto": ("veiculos",),
        "terreno": ("terrenos", "imoveis"),
        "predio": ("imoveis",),
        "edificio": ("imoveis",),
        "reforma": ("obras", "benfeitorias"),
        "obra": ("obras", "benfeitorias"),
        "condicionado": ("aparelho", "ar"),
    }
    query_terms = [term for term in re.findall(r"[\w]+", _key(query)) if len(term) > 1 and term not in stopwords]
    terms = list(dict.fromkeys(query_terms + [alias for term in query_terms for alias in aliases.get(term, ())]))
    query_code = query.strip().casefold()
    kind_words = {"movel": ("bem movel", "bens moveis"), "imovel": ("bem imovel", "bens imoveis")}.get(kind, ())
    results: list[tuple[int, dict[str, str | int]]] = []
    for record in records:
        code = record["code"]
        title = record["title"]
        function = record["function"]
        status = record["status"]
        if status and _key(status) not in {"ativa", "ativo"}:
            continue
        normalized_title = _key(title)
        normalized_function = _key(function)
        searchable = f"{normalized_title} {normalized_function} {_key(code)}"
        score = 0
        if query_code and query_code == code.casefold():
            score += 100
        for term in terms:
            if term in normalized_title:
                score += 7 if normalized_title.startswith(term) else 5
            if term in normalized_function:
                score += 2
            if term in _key(code):
                score += 3
        matched_terms = sum(1 for term in terms if term in searchable)
        if not terms or not score or (terms and matched_terms == 0):
            continue
        if kind_words and any(phrase in searchable for phrase in kind_words):
            score += 4
        result = dict(record)
        results.append((score, result))
    results.sort(key=lambda item: (-item[0], str(item[1]["code"])))
    return [dict(score=score, **result) for score, result in results[:15]]
