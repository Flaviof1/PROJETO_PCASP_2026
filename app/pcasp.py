"""Importação e consulta dos dados PCASP no banco local."""

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

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
    connection.execute(
        """CREATE TABLE IF NOT EXISTS inventory_review_decisions (
            asset_key TEXT PRIMARY KEY,
            asset_code TEXT NOT NULL DEFAULT '',
            plate TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            source_account TEXT NOT NULL DEFAULT '',
            decision TEXT NOT NULL CHECK(decision IN ('approved', 'keep')),
            account_code TEXT NOT NULL DEFAULT '',
            account_title TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        )"""
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_accounts_status ON accounts(status)")


def get_inventory_review_decisions() -> dict[str, dict[str, str]]:
    connection = connect()
    try:
        _schema(connection)
        rows = connection.execute("SELECT * FROM inventory_review_decisions").fetchall()
        return {row["asset_key"]: dict(row) for row in rows}
    finally:
        connection.close()


def save_inventory_review_decision(decision: dict[str, str]) -> None:
    connection = connect()
    try:
        _schema(connection)
        with connection:
            connection.execute(
                """INSERT INTO inventory_review_decisions
                   (asset_key, asset_code, plate, description, source_account, decision,
                    account_code, account_title, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(asset_key) DO UPDATE SET
                    asset_code=excluded.asset_code, plate=excluded.plate,
                    description=excluded.description, source_account=excluded.source_account,
                    decision=excluded.decision, account_code=excluded.account_code,
                    account_title=excluded.account_title, updated_at=excluded.updated_at""",
                (decision["asset_key"], decision["asset_code"], decision["plate"],
                 decision["description"], decision["source_account"], decision["decision"],
                 decision["account_code"], decision["account_title"], decision["updated_at"]),
            )
    finally:
        connection.close()


def delete_inventory_review_decisions() -> int:
    connection = connect()
    try:
        _schema(connection)
        with connection:
            cursor = connection.execute("DELETE FROM inventory_review_decisions")
            return cursor.rowcount
    finally:
        connection.close()


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


def _add_hierarchy(connection: sqlite3.Connection, results: list[dict[str, Any]]) -> None:
    levels = ("Classe", "Grupo", "Subgrupo", "Título", "Subtítulo", "Item", "Subitem")
    codes_by_account: dict[str, list[tuple[str, str]]] = {}
    codes: set[str] = set()
    for account in results:
        parts = str(account["code"]).split(".")
        ancestors: list[tuple[str, str]] = []
        seen: set[str] = set()
        for index, level in enumerate(levels[: min(len(parts), len(levels))]):
            suffix = ["0" if slot < 5 else "00" for slot in range(index + 1, len(levels))]
            parent_code = ".".join(parts[: index + 1] + suffix)
            if parent_code not in seen:
                ancestors.append((level, parent_code))
                codes.add(parent_code)
                seen.add(parent_code)
        codes_by_account[str(account["code"])] = ancestors

    if not codes:
        return
    placeholders = ",".join("?" for _ in codes)
    titles = {
        row["code"]: row["title"]
        for row in connection.execute(
            f"SELECT code, title FROM accounts WHERE code IN ({placeholders})", tuple(codes)
        )
    }
    for account in results:
        account["hierarchy"] = [
            {"level": level, "code": code, "title": titles[code]}
            for level, code in codes_by_account[str(account["code"])]
            if code in titles
        ]


def build_search_index(records: list[Any]) -> tuple[list[tuple[Any, str, str, str, str]], dict[str, set[int]]]:
    prepared = [
        (record, _key(record["title"]), _key(record["function"]), _key(record["code"]), _key(record["status"]))
        for record in records
    ]
    postings: dict[str, set[int]] = defaultdict(set)
    for index, (_, title, function, code, _) in enumerate(prepared):
        for text in (title, function, code):
            for token in re.findall(r"[\w]+", text):
                gram_size = 2 if len(token) == 2 else 3
                if len(token) < gram_size:
                    continue
                for position in range(len(token) - gram_size + 1):
                    postings[token[position : position + gram_size]].add(index)
    return prepared, dict(postings)


def search_accounts(
    query: str,
    kind: str = "",
    limit: int = 15,
    offset: int = 0,
    *,
    _records: list[Any] | None = None,
    _prepared_records: list[tuple[Any, str, str, str, str]] | None = None,
    _substring_index: dict[str, set[int]] | None = None,
    _include_hierarchy: bool = True,
) -> list[dict[str, Any]]:
    if _prepared_records is None and _records is None:
        connection = connect()
        try:
            records = connection.execute(
                "SELECT code, title, function, balance_nature, status, details FROM accounts"
            ).fetchall()
        finally:
            connection.close()
    elif _records is not None:
        records = _records
    else:
        records = []
    if _prepared_records is None:
        prepared_records = [
            (record, _key(record["title"]), _key(record["function"]), _key(record["code"]), _key(record["status"]))
            for record in records
        ]
    else:
        prepared_records = _prepared_records

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
    query_digits = re.sub(r"\D", "", query)
    kind_words = {"movel": ("bem movel", "bens moveis"), "imovel": ("bem imovel", "bens imoveis")}.get(kind, ())
    results: list[tuple[int, dict[str, Any]]] = []
    if _substring_index is not None:
        candidate_ids: set[int] = set()
        for term in terms:
            gram_size = 2 if len(term) == 2 else 3
            if len(term) < gram_size:
                continue
            postings = [_substring_index.get(term[position : position + gram_size], set())
                        for position in range(len(term) - gram_size + 1)]
            if postings and all(postings):
                matches = set.intersection(*(set(posting) for posting in postings))
                candidate_ids.update(matches)
        if len(query_digits) >= 8:
            candidate_ids.update(
                index for index, (record, *_rest) in enumerate(prepared_records)
                if query_digits == re.sub(r"\D", "", str(record["code"]))
            )
        candidates = (prepared_records[index] for index in candidate_ids)
    else:
        candidates = iter(prepared_records)
    for record, normalized_title, normalized_function, normalized_code, normalized_status in candidates:
        code = record["code"]
        title = record["title"]
        function = record["function"]
        status = record["status"]
        if status and normalized_status not in {"ativa", "ativo"}:
            continue
        searchable = f"{normalized_title} {normalized_function} {normalized_code}"
        score = 0
        reasons: list[str] = []
        exact_code_match = bool(query_digits) and query_digits == re.sub(r"\D", "", code)
        if (query_code and query_code == code.casefold()) or exact_code_match:
            score += 100
            reasons.append("O código da conta corresponde exatamente à busca, com ou sem pontuação.")
        for term in terms:
            if term in normalized_title:
                score += 7 if normalized_title.startswith(term) else 5
            if term in normalized_function:
                score += 2
            if term in normalized_code:
                score += 3
        for term in query_terms:
            if term in normalized_title:
                reasons.append(f'O título contém “{term}”.')
            if term in normalized_function:
                reasons.append(f'A função contém “{term}”.')
            related_matches = [
                alias for alias in aliases.get(term, ())
                if alias in normalized_title or alias in normalized_function
            ]
            if related_matches:
                reasons.append(f'O termo “{term}” encontrou termos relacionados: {", ".join(related_matches)}.')
        matched_terms = sum(1 for term in terms if term in searchable)
        if not terms or not score or (terms and matched_terms == 0 and not exact_code_match):
            continue
        if kind_words and any(phrase in searchable for phrase in kind_words):
            score += 4
        result = dict(record)
        result["match_reasons"] = reasons or ["A conta corresponde aos termos relacionados encontrados na busca."]
        results.append((score, result))
    results.sort(key=lambda item: (-item[0], str(item[1]["code"])))
    start = max(0, offset)
    selected = [dict(score=score, **result) for score, result in results[start : start + max(1, limit)]]
    if _include_hierarchy:
        connection = connect()
        try:
            _add_hierarchy(connection, selected)
        finally:
            connection.close()
    return selected
