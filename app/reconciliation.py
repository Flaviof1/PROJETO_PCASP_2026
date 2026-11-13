"""Leitura em memória dos arquivos de inventário e relatório PCASP."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from app.pcasp import (
    connect,
    get_inventory_review_decisions,
    save_inventory_review_decision as _save_inventory_review_decision,
)
from app.xlsx_reader import SpreadsheetError


def _key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _review_asset_key(asset_code: str, plate: str) -> str:
    identity = json.dumps([asset_code.strip(), plate.strip()], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _money(value: str) -> Decimal:
    value = value.strip().replace("R$", "").replace(" ", "")
    if not value:
        return Decimal(0)
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise SpreadsheetError(f"Valor monetário inválido no arquivo: {value}") from exc


def _brl(value: Decimal) -> str:
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _format_code(code: str) -> str:
    digits = _digits(code)
    if len(digits) == 9:
        return ".".join((digits[0], digits[1], digits[2], digits[3], digits[4], digits[5:7], digits[7:9]))
    return code


_REVIEW_STOPWORDS = {
    "com", "sem", "para", "por", "das", "dos", "uma", "uns", "nas", "nos",
    "bem", "bens", "novo", "nova", "usado", "usada", "cor", "azul", "branco",
    "preto", "marca", "modelo", "tipo", "geral", "outro", "outros", "unidade",
}
_REVIEW_GROUPS = {
    "mobiliario": "mobiliario", "mobiliarios": "mobiliario", "moveis": "mobiliario", "movel": "mobiliario",
    "cadeira": "mobiliario", "cadeiras": "mobiliario", "poltrona": "mobiliario", "poltronas": "mobiliario",
    "sofa": "mobiliario", "sofas": "mobiliario", "mesa": "mobiliario", "mesas": "mobiliario",
    "armario": "mobiliario", "armarios": "mobiliario", "estante": "mobiliario", "estantes": "mobiliario",
    "informatica": "informatica", "computador": "informatica", "computadores": "informatica",
    "notebook": "informatica", "notebooks": "informatica", "laptop": "informatica", "desktop": "informatica",
    "impressora": "informatica", "impressoras": "informatica", "scanner": "informatica", "monitor": "informatica",
    "processamento": "informatica", "tecnologia": "informatica", "dados": "informatica",
    "veiculo": "veiculos", "veiculos": "veiculos", "carro": "veiculos", "automovel": "veiculos",
    "caminhonete": "veiculos", "caminhao": "veiculos", "moto": "veiculos", "onibus": "veiculos",
    "imovel": "imoveis", "imoveis": "imoveis", "edificio": "imoveis", "edificios": "imoveis",
    "predio": "imoveis", "predios": "imoveis", "terreno": "imoveis", "terrenos": "imoveis",
}
_REVIEW_GROUP_LABELS = {
    "mobiliario": "mobiliário", "informatica": "informática e processamento de dados",
    "veiculos": "veículos", "imoveis": "imóveis",
}


def _review_terms(value: str) -> set[str]:
    terms = set()
    for token in re.findall(r"[\w]+", _key(value)):
        if len(token) < 4 or token in _REVIEW_STOPWORDS:
            continue
        terms.add(_REVIEW_GROUPS.get(token, token))
    return terms


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise SpreadsheetError("Não consegui ler a codificação do arquivo.")


def _read_inventory(data: bytes) -> tuple[dict[str, Decimal], dict[str, int], int]:
    text = _decode(data)
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    if not reader.fieldnames:
        raise SpreadsheetError("O CSV do inventário está vazio ou sem cabeçalho.")
    columns = {_key(name.strip()): name for name in reader.fieldnames if name}
    account_column = columns.get("conta bem")
    value_column = columns.get("valor atual")
    if not account_column or not value_column:
        raise SpreadsheetError("O CSV precisa conter as colunas 'Conta Bem' e 'Valor Atual'.")

    totals: dict[str, Decimal] = defaultdict(Decimal)
    counts: dict[str, int] = defaultdict(int)
    count = 0
    for row in reader:
        code = _digits(row.get(account_column, ""))
        if not code:
            continue
        amount = _money(row.get(value_column, ""))
        totals[code] += amount
        counts[code] += 1
        count += 1
    if not count:
        raise SpreadsheetError("Não encontrei bens com código preenchido na coluna 'Conta Bem'.")
    return dict(totals), dict(counts), count


def suggest_inventory_reviews(data: bytes, system_accounts_data: bytes) -> dict:
    reader = csv.DictReader(io.StringIO(_decode(data)), delimiter=";")
    if not reader.fieldnames:
        raise SpreadsheetError("O CSV do inventário está vazio ou sem cabeçalho.")
    columns = {_key(name.strip()): name for name in reader.fieldnames if name}
    required = {"conta bem", "descricao", "plaqueta"}
    if required - columns.keys():
        raise SpreadsheetError("O CSV precisa conter as colunas 'Conta Bem', 'Descrição' e 'Plaqueta'.")
    code_column = columns.get("codigo")
    account_column = columns["conta bem"]
    description_column = columns["descricao"]
    plate_column = columns["plaqueta"]

    connection = connect()
    try:
        records = connection.execute(
            "SELECT code, title, function, balance_nature, status, details FROM accounts"
        ).fetchall()
    finally:
        connection.close()
    if not records:
        raise SpreadsheetError("Carregue primeiro a tabela PCASP para gerar sugestões.")
    account_map, _ = _read_system_account_map(system_accounts_data)
    system_pcasp_codes = set(account_map.values())
    account_by_code = {_digits(str(record["code"])): record for record in records}
    titles = {code: record["title"] for code, record in account_by_code.items()}
    prepared_records = []
    term_index: dict[str, set[int]] = defaultdict(set)
    for record in records:
        # “Conta Bem” classifies patrimonial assets; expense, revenue and control
        # accounts may share words with an item's description but are not candidates.
        if not _digits(str(record["code"])).startswith("123"):
            continue
        idx = len(prepared_records)
        title_terms = _review_terms(str(record["title"] or ""))
        function_terms = _review_terms(str(record["function"] or ""))
        prepared_records.append((record, title_terms, function_terms))
        for term in title_terms | function_terms:
            term_index[term].add(idx)

    cache: dict[str, list[dict[str, Any]]] = {}
    recommendations = []
    item_count = 0
    characteristic_labels = (
        ("produto", "Produto"),
        ("conta dae", "Conta de depreciação (DAE)"),
        ("conta despesa", "Conta de despesa"),
        ("conta resultado", "Conta de resultado"),
        ("cod setor atual", "Código do setor atual"),
        ("tipo", "Tipo"),
        ("modelo", "Modelo"),
        ("classificacao", "Classificação"),
        ("data", "Data de aquisição"),
        ("valor inicial", "Valor inicial"),
        ("vida util inicial", "Vida útil inicial"),
        ("vida util atual", "Vida útil atual"),
        ("valor residual", "Valor residual"),
        ("valor atual", "Valor atual"),
        ("setor atual", "Setor atual"),
    )
    for row_index, row in enumerate(reader):
        description = (row.get(description_column) or "").strip()
        if not description:
            continue
        item_count += 1
        raw_current_code = _digits(row.get(account_column, ""))
        current_code = account_map.get(raw_current_code, raw_current_code if raw_current_code in account_by_code else "")
        query_terms = _review_terms(description[:300])
        cache_key = " ".join(sorted(query_terms))
        if cache_key not in cache:
            candidate_ids = set().union(*(term_index.get(term, set()) for term in query_terms)) if query_terms else set()
            ranked = []
            for idx in candidate_ids:
                record, title_terms, function_terms = prepared_records[idx]
                title_hits = query_terms & title_terms
                function_hits = query_terms & function_terms
                score = 3 * len(title_hits) + len(function_hits)
                if score >= 3:
                    ranked.append({
                        "code": str(record["code"]), "title": str(record["title"] or ""),
                        "function": str(record["function"] or ""),
                        "balance_nature": str(record["balance_nature"] or ""),
                        "status": str(record["status"] or ""), "details": str(record["details"] or ""),
                        "available_in_system": _digits(str(record["code"])) in system_pcasp_codes,
                        "score": score, "matched_terms": title_hits | function_hits,
                    })
            cache[cache_key] = sorted(
                ranked,
                key=lambda item: (not item["available_in_system"], -item["score"], item["code"]),
            )
        ranked = cache[cache_key]
        current_match = next((item for item in ranked if _digits(item["code"]) == current_code), None)
        alternatives = [item for item in ranked if _digits(item["code"]) != current_code]
        if not alternatives:
            continue
        available_alternatives = [item for item in alternatives if item["available_in_system"]]
        best = available_alternatives[0] if available_alternatives else alternatives[0]
        current_score = current_match["score"] if current_match else 0
        if best["score"] < 3 or best["score"] - current_score < 3:
            continue
        suggestions = [
            {
                "code": item["code"],
                "title": item["title"],
                "function": item["function"],
                "balance_nature": item["balance_nature"],
                "status": item["status"],
                "details": item["details"],
                "available_in_system": item["available_in_system"],
                "reasons": [
                    _REVIEW_GROUP_LABELS.get(term, term)
                    for term in sorted(item["matched_terms"])
                ][:3],
            }
            for item in alternatives[:3]
        ]
        recommendations.append({
            "row_index": row_index,
            "asset_code": (row.get(code_column) or "").strip() if code_column else "",
            "plate": (row.get(plate_column) or "").strip(),
            "source_account": (row.get(account_column) or "").strip(),
            "description": description,
            "current_code": _format_code(current_code) if current_code else ("Conta atual sem correspondência" if raw_current_code else "Sem conta"),
            "current_title": titles.get(current_code, "Conta atual não localizada na relação do SH3"),
            "current_available_in_system": current_code in system_pcasp_codes,
            "current_function": account_by_code[current_code]["function"] if current_code in account_by_code else "",
            "current_balance_nature": account_by_code[current_code]["balance_nature"] if current_code in account_by_code else "",
            "current_status": account_by_code[current_code]["status"] if current_code in account_by_code else "",
            "current_account_details": account_by_code[current_code]["details"] if current_code in account_by_code else "",
            "characteristics": [
                {"label": label, "value": (row.get(columns.get(column, "")) or "").strip()}
                for column, label in characteristic_labels
                if columns.get(column) and (row.get(columns[column]) or "").strip()
            ],
            "suggestions": suggestions,
            "guidance": "No cadastro patrimonial, localize o bem pela plaqueta e confira o campo Conta Bem. A conta sugerida é apenas uma possibilidade para análise.",
        })
    saved_decisions = get_inventory_review_decisions()
    pcasp_codes = set(account_by_code)
    for item in recommendations:
        saved = saved_decisions.get(_review_asset_key(item["asset_code"], item["plate"]))
        if not saved:
            continue
        source_matches = saved["source_account"] == item["source_account"]
        already_applied = (
            saved["decision"] == "approved"
            and _digits(item["source_account"]) == _digits(saved["account_code"])
        )
        if not source_matches and not already_applied:
            continue
        if saved["decision"] == "approved":
            code = _digits(saved["account_code"])
            if code not in pcasp_codes or code not in system_pcasp_codes:
                continue
            title = titles.get(code, saved["account_title"])
        else:
            code = ""
            title = ""
        item["saved_decision"] = {
            "decision": saved["decision"],
            "account_code": code,
            "account_title": title,
            "updated_at": saved["updated_at"],
        }
    return {
        "item_count": item_count,
        "review_count": len(recommendations),
        "unique_descriptions": len(cache),
        "unavailable_suggestion_codes": len({
            suggestion["code"]
            for item in recommendations
            for suggestion in item["suggestions"]
            if not suggestion["available_in_system"]
        }),
        "recommendations": recommendations,
        "note": "As contas candidatas são comparadas ao PCASP e à relação do SH3. Candidatas ausentes da relação são identificadas como não cadastradas e não podem ser aprovadas nem exportadas. A indicação textual não confirma erro ou classificação correta.",
    }


def save_inventory_review_decision(decision_data: bytes, system_accounts_data: bytes) -> None:
    try:
        payload = json.loads(decision_data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SpreadsheetError("A decisão de revisão recebida está inválida.") from exc
    if not isinstance(payload, dict):
        raise SpreadsheetError("A decisão de revisão recebida está inválida.")
    asset_code = str(payload.get("asset_code", "")).strip()
    plate = str(payload.get("plate", "")).strip()
    description = str(payload.get("description", "")).strip()
    source_account = str(payload.get("source_account", "")).strip()
    decision = str(payload.get("decision", ""))
    account_code = _digits(str(payload.get("account_code", "")))
    if not (asset_code or plate):
        raise SpreadsheetError("O bem precisa ter código ou plaqueta para salvar a decisão.")
    if decision not in {"approved", "keep"}:
        raise SpreadsheetError("A decisão precisa ser aprovar uma conta ou manter a conta atual.")
    account_title = ""
    if decision == "approved":
        account_map, _ = _read_system_account_map(system_accounts_data)
        if len(account_code) != 9 or account_code not in set(account_map.values()):
            raise SpreadsheetError("A conta aprovada não consta na relação do SH3 e não pode ser salva.")
        connection = connect()
        try:
            rows = connection.execute("SELECT code, title FROM accounts").fetchall()
            row = next((item for item in rows if _digits(str(item["code"])) == account_code), None)
        finally:
            connection.close()
        if not row:
            raise SpreadsheetError("A conta aprovada não consta na tabela PCASP carregada.")
        account_title = str(row["title"] or "")
    _save_inventory_review_decision({
        "asset_key": _review_asset_key(asset_code, plate),
        "asset_code": asset_code,
        "plate": plate,
        "description": description,
        "source_account": source_account,
        "decision": decision,
        "account_code": account_code if decision == "approved" else "",
        "account_title": account_title,
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    })


def export_approved_changes(
    inventory_data: bytes,
    approvals_data: bytes,
    system_accounts_data: bytes | None = None,
) -> bytes:
    import json

    try:
        approvals = json.loads(approvals_data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SpreadsheetError("As aprovações recebidas estão inválidas.") from exc
    if not isinstance(approvals, list) or not approvals:
        raise SpreadsheetError("Não há alterações aprovadas para exportar.")
    requested: dict[int, str] = {}
    for approval in approvals:
        if not isinstance(approval, dict):
            raise SpreadsheetError("Uma das aprovações está inválida.")
        try:
            row_index = int(approval["row_index"])
            code = _digits(str(approval["account_code"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise SpreadsheetError("Uma aprovação não informa linha e conta válidas.") from exc
        if row_index < 0 or len(code) != 9:
            raise SpreadsheetError("Uma aprovação contém uma conta PCASP inválida.")
        requested[row_index] = code

    connection = connect()
    try:
        valid_codes = {_digits(row["code"]) for row in connection.execute("SELECT code FROM accounts")}
    finally:
        connection.close()
    if any(code not in valid_codes for code in requested.values()):
        raise SpreadsheetError("Uma conta aprovada não existe na tabela PCASP carregada. Atualize a análise e tente novamente.")
    if system_accounts_data is not None:
        allowed_codes = set(_read_system_account_map(system_accounts_data)[0].values())
        if any(code not in allowed_codes for code in requested.values()):
            raise SpreadsheetError("Uma conta aprovada não está cadastrada na relação do SH3. Ela não pode ser exportada.")

    reader = csv.reader(io.StringIO(_decode(inventory_data)), delimiter=";")
    try:
        headers = next(reader)
    except StopIteration as exc:
        raise SpreadsheetError("O CSV do inventário está vazio.") from exc
    columns = {_key(name.strip()): index for index, name in enumerate(headers) if name}
    account_index = columns.get("conta bem")
    if account_index is None:
        raise SpreadsheetError("Não encontrei a coluna 'Conta Bem' no CSV.")
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";", lineterminator="\r\n")
    writer.writerow(headers)
    applied = set()
    row_index = 0
    for values in reader:
        if not values:
            continue
        if row_index in requested:
            while len(values) <= account_index:
                values.append("")
            values[account_index] = requested[row_index]
            applied.add(row_index)
        writer.writerow(values)
        row_index += 1
    if applied != requested.keys():
        raise SpreadsheetError("Algum bem aprovado não existe mais no arquivo. Faça uma nova análise antes de exportar.")
    try:
        return output.getvalue().encode("cp1252")
    except UnicodeEncodeError as exc:
        raise SpreadsheetError("O CSV contém caracteres que não podem ser salvos em Windows-1252.") from exc


def _read_system_account_map(data: bytes) -> tuple[dict[str, str], dict[str, str]]:
    reader = csv.DictReader(io.StringIO(_decode(data)), delimiter=";")
    if not reader.fieldnames:
        raise SpreadsheetError("A relação de contas do SH3 está vazia ou sem cabeçalho.")
    columns = {_key(name.strip().rstrip(":")): name for name in reader.fieldnames if name}
    id_column = columns.get("codigo")
    patrimonial_column = columns.get("conta patrimonial")
    state_column = columns.get("conta patrimonial estadual")
    title_column = columns.get("titulo")
    if not id_column or not patrimonial_column or not state_column or not title_column:
        raise SpreadsheetError(
            "A relação do SH3 precisa conter Código, Título, Conta Patrimonial Estadual e Conta Patrimonial."
        )
    mapping: dict[str, str] = {}
    titles: dict[str, str] = {}
    for row in reader:
        target = _digits(row.get(patrimonial_column, ""))
        state_code = _digits(row.get(state_column, ""))
        local_code = _digits(row.get(id_column, ""))
        if len(target) != 9 or len(state_code) != 9:
            continue
        titles[target] = (row.get(title_column) or "").strip()
        for alias in (local_code, state_code, target):
            if not alias:
                continue
            existing = mapping.get(alias)
            if existing and existing != target:
                raise SpreadsheetError(
                    f"O código {alias} aparece ligado a mais de uma conta na relação do SH3."
                )
            mapping[alias] = target
    if not mapping:
        raise SpreadsheetError("Não encontrei contas patrimoniais válidas na relação do SH3.")
    return mapping, titles


def _excel_cell_text(reference: str, value: str, style: int = 0) -> str:
    return (
        f'<c r="{reference}" s="{style}" t="inlineStr"><is><t xml:space="preserve">'
        f'{escape(value)}</t></is></c>'
    )


def _excel_cell_number(reference: str, value: Decimal, style: int = 0) -> str:
    return f'<c r="{reference}" s="{style}"><v>{format(value, "f")}</v></c>'


def _build_account_summary_xlsx(
    before_totals: dict[str, Decimal],
    after_totals: dict[str, Decimal],
    titles: dict[str, str],
    excluded: list[dict[str, str]],
    changed_items: list[dict[str, str]],
) -> bytes:
    codes = sorted(set(before_totals) | set(after_totals))
    if not codes:
        raise SpreadsheetError("Não há valores por conta para incluir no resumo.")
    last_data_row = 4 + len(codes)
    total_row = last_data_row + 1
    rows = [
        '<row r="1" ht="30" customHeight="1">' + _excel_cell_text("A1", "COMPARATIVO DE BENS POR CONTA PATRIMONIAL", 1) + "</row>",
        '<row r="2">' + _excel_cell_text("A2", "Antes: inventário original. Depois: inventário após aplicar as contas aprovadas.", 2) + "</row>",
        '<row r="3"/>',
        '<row r="4">' + "".join((
            _excel_cell_text("A4", "Conta Patrimonial", 3),
            _excel_cell_text("B4", "Descrição da Conta", 3),
            _excel_cell_text("C4", "Valor antes", 3),
            _excel_cell_text("D4", "Valor depois", 3),
            _excel_cell_text("E4", "Variação", 3),
        )) + "</row>",
    ]
    for row_number, code in enumerate(codes, start=5):
        rows.append(
            f'<row r="{row_number}">'
            + _excel_cell_text(f"A{row_number}", _format_code(code), 4)
            + _excel_cell_text(f"B{row_number}", titles.get(code, ""), 4)
            + _excel_cell_number(f"C{row_number}", before_totals.get(code, Decimal(0)), 5)
            + _excel_cell_number(f"D{row_number}", after_totals.get(code, Decimal(0)), 5)
            + _excel_cell_number(
                f"E{row_number}",
                after_totals.get(code, Decimal(0)) - before_totals.get(code, Decimal(0)),
                5,
            )
            + "</row>"
        )
    rows.append(
        f'<row r="{total_row}">'
        + _excel_cell_text(f"A{total_row}", "TOTAL GERAL", 6)
        + _excel_cell_text(f"B{total_row}", "", 6)
        + _excel_cell_number(f"C{total_row}", sum(before_totals.values(), Decimal(0)), 7)
        + _excel_cell_number(f"D{total_row}", sum(after_totals.values(), Decimal(0)), 7)
        + _excel_cell_number(
            f"E{total_row}",
            sum(after_totals.values(), Decimal(0)) - sum(before_totals.values(), Decimal(0)),
            7,
        )
        + "</row>"
    )
    if excluded:
        section_row = total_row + 2
        rows.append(
            f'<row r="{section_row}">'
            + _excel_cell_text(f"A{section_row}", "BENS EXCLUÍDOS DO RESUMO", 6)
            + "</row>"
        )
        header_row = section_row + 1
        rows.append(
            f'<row r="{header_row}">' + "".join((
                _excel_cell_text(f"A{header_row}", "Plaqueta", 3),
                _excel_cell_text(f"B{header_row}", "Conta Bem informada", 3),
                _excel_cell_text(f"C{header_row}", "Valor não somado", 3),
            )) + "</row>"
        )
        for row_number, item in enumerate(excluded, start=header_row + 1):
            rows.append(
                f'<row r="{row_number}">'
                + _excel_cell_text(f"A{row_number}", item["plate"] or "Não informada", 4)
                + _excel_cell_text(f"B{row_number}", item["account"] or "Conta Bem vazia", 4)
                + _excel_cell_number(f"C{row_number}", Decimal(item["value"]), 5)
                + "</row>"
            )
    worksheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="4" topLeftCell="A5" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        '<sheetFormatPr defaultRowHeight="18"/><cols>'
        '<col min="1" max="1" width="24" customWidth="1"/>'
        '<col min="2" max="2" width="56" customWidth="1"/>'
        '<col min="3" max="5" width="22" customWidth="1"/>'
        '</cols><sheetData>' + "".join(rows) + '</sheetData>'
        f'<autoFilter ref="A4:E{last_data_row}"/>'
        '<mergeCells count="2"><mergeCell ref="A1:E1"/><mergeCell ref="A2:E2"/></mergeCells>'
        '<pageMargins left="0.3" right="0.3" top="0.5" bottom="0.5" header="0.2" footer="0.2"/>'
        '</worksheet>'
    )
    item_rows = [
        '<row r="1" ht="30" customHeight="1">' + _excel_cell_text("A1", "DETALHAMENTO DOS ITENS COM CONTA ALTERADA", 1) + "</row>",
        '<row r="2">' + _excel_cell_text("A2", "Confira plaqueta, código e valor de cada bem que compõe as alterações do comparativo.", 2) + "</row>",
        '<row r="3"/>',
        '<row r="4">' + "".join((
            _excel_cell_text("A4", "Plaqueta", 3),
            _excel_cell_text("B4", "Código do bem", 3),
            _excel_cell_text("C4", "Descrição do bem", 3),
            _excel_cell_text("D4", "Conta anterior", 3),
            _excel_cell_text("E4", "Descrição da conta anterior", 3),
            _excel_cell_text("F4", "Conta nova", 3),
            _excel_cell_text("G4", "Descrição da conta nova", 3),
            _excel_cell_text("H4", "Valor do item", 3),
        )) + "</row>",
    ]
    for row_number, item in enumerate(changed_items, start=5):
        item_rows.append(
            f'<row r="{row_number}">'
            + _excel_cell_text(f"A{row_number}", item["plate"] or "Não informada", 4)
            + _excel_cell_text(f"B{row_number}", item["asset_code"] or "Não informado", 4)
            + _excel_cell_text(f"C{row_number}", item["description"] or "Sem descrição", 4)
            + _excel_cell_text(f"D{row_number}", _format_code(item["old_code"]) if item["old_code"] else item["old_account"], 4)
            + _excel_cell_text(f"E{row_number}", item["old_title"], 4)
            + _excel_cell_text(f"F{row_number}", _format_code(item["new_code"]) if item["new_code"] else item["new_account"], 4)
            + _excel_cell_text(f"G{row_number}", item["new_title"], 4)
            + _excel_cell_number(f"H{row_number}", Decimal(item["value"]), 5)
            + "</row>"
        )
    if not changed_items:
        item_rows.append('<row r="5">' + _excel_cell_text("A5", "Nenhum item teve a conta alterada nesta exportação.", 2) + "</row>")
    item_last_row = max(4 + len(changed_items), 5)
    items_worksheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="4" topLeftCell="A5" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        '<sheetFormatPr defaultRowHeight="18"/><cols>'
        '<col min="1" max="2" width="18" customWidth="1"/>'
        '<col min="3" max="3" width="42" customWidth="1"/>'
        '<col min="4" max="4" width="22" customWidth="1"/>'
        '<col min="5" max="5" width="38" customWidth="1"/>'
        '<col min="6" max="6" width="22" customWidth="1"/>'
        '<col min="7" max="7" width="38" customWidth="1"/>'
        '<col min="8" max="8" width="20" customWidth="1"/>'
        '</cols><sheetData>' + "".join(item_rows) + '</sheetData>'
        f'<autoFilter ref="A4:H{item_last_row}"/>'
        '<mergeCells count="2"><mergeCell ref="A1:H1"/><mergeCell ref="A2:H2"/></mergeCells>'
        '<pageMargins left="0.3" right="0.3" top="0.5" bottom="0.5" header="0.2" footer="0.2"/>'
        '</worksheet>'
    )
    styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
      <numFmts count="1"><numFmt numFmtId="164" formatCode="&quot;R$&quot; #,##0.00;[Red]-&quot;R$&quot; #,##0.00"/></numFmts>
      <fonts count="5"><font><sz val="11"/><name val="Calibri"/><color rgb="FF26332C"/></font>
        <font><b/><sz val="18"/><name val="Calibri"/><color rgb="FFFFFFFF"/></font>
        <font><i/><sz val="10"/><name val="Calibri"/><color rgb="FF607067"/></font>
        <font><b/><sz val="11"/><name val="Calibri"/><color rgb="FFFFFFFF"/></font>
        <font><b/><sz val="11"/><name val="Calibri"/><color rgb="FF245B45"/></font>
      </fonts>
      <fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>
        <fill><patternFill patternType="solid"><fgColor rgb="FF245B45"/><bgColor indexed="64"/></patternFill></fill>
        <fill><patternFill patternType="solid"><fgColor rgb="FFE8F2EB"/><bgColor indexed="64"/></patternFill></fill>
      </fills>
      <borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border>
        <border><left/><right/><top/><bottom style="thin"><color rgb="FFD9E2DC"/></bottom><diagonal/></border>
      </borders>
      <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
      <cellXfs count="8">
        <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
        <xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center"/></xf>
        <xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0"/>
        <xf numFmtId="0" fontId="3" fillId="2" borderId="1" xfId="0" applyAlignment="1"><alignment vertical="center"/></xf>
        <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0"/>
        <xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1"/>
        <xf numFmtId="0" fontId="4" fillId="3" borderId="1" xfId="0"/>
        <xf numFmtId="164" fontId="4" fillId="3" borderId="1" xfId="0" applyNumberFormat="1"/>
      </cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
    </styleSheet>'''
    package_files = {
        "[Content_Types].xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
          <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
          <Default Extension="xml" ContentType="application/xml"/>
          <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
          <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
          <Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
          <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
        </Types>''',
        "_rels/.rels": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
          <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
        </Relationships>''',
        "xl/workbook.xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
          <sheets><sheet name="Resumo por conta" sheetId="1" r:id="rId1"/><sheet name="Itens alterados" sheetId="2" r:id="rId2"/></sheets>
        </workbook>''',
        "xl/_rels/workbook.xml.rels": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
          <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
          <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
          <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
        </Relationships>''',
        "xl/styles.xml": styles,
        "xl/worksheets/sheet1.xml": worksheet,
        "xl/worksheets/sheet2.xml": items_worksheet,
    }
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as book:
        for path, content in package_files.items():
            book.writestr(path, content.encode("utf-8"))
    return output.getvalue()


def export_account_summary(
    inventory_data: bytes, approvals_data: bytes, system_accounts_data: bytes
) -> bytes:
    """Gera Conta Bem x valor usando a relação SH3 para converter códigos internos."""
    import json

    try:
        approvals = json.loads(approvals_data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SpreadsheetError("As aprovações recebidas estão inválidas.") from exc
    if not isinstance(approvals, list):
        raise SpreadsheetError("As aprovações recebidas estão inválidas.")
    account_map, account_titles = _read_system_account_map(system_accounts_data)
    system_pcasp_codes = set(account_map.values())
    final_inventory = export_approved_changes(inventory_data, approvals_data, system_accounts_data) if approvals else inventory_data
    if any(_digits(str(item.get("account_code", ""))) not in system_pcasp_codes for item in approvals if isinstance(item, dict)):
        raise SpreadsheetError("Há uma conta aprovada que não consta na relação do SH3. Confira a opção antes de gerar o resumo.")

    def summarize(data: bytes) -> tuple[dict[str, Decimal], list[dict[str, str]]]:
        reader = csv.DictReader(io.StringIO(_decode(data)), delimiter=";")
        if not reader.fieldnames:
            raise SpreadsheetError("O CSV do inventário está vazio ou sem cabeçalho.")
        columns = {_key(name.strip()): name for name in reader.fieldnames if name}
        account_column = columns.get("conta bem")
        value_column = columns.get("valor atual")
        plate_column = columns.get("plaqueta")
        if not account_column or not value_column:
            raise SpreadsheetError("O inventário precisa conter 'Conta Bem' e 'Valor Atual'.")
        totals: dict[str, Decimal] = defaultdict(Decimal)
        excluded: list[dict[str, str]] = []
        for row in reader:
            raw_account = (row.get(account_column) or "").strip()
            target_code = account_map.get(_digits(raw_account))
            value = _money(row.get(value_column) or "")
            if not raw_account or not target_code:
                plate = (row.get(plate_column) or "").strip() if plate_column else ""
                excluded.append({"plate": plate, "account": raw_account, "value": str(value)})
                continue
            totals[target_code] += value
        return dict(totals), excluded

    before_totals, _ = summarize(inventory_data)
    after_totals, excluded = summarize(final_inventory)
    if not after_totals:
        raise SpreadsheetError("Nenhuma conta do inventário corresponde à relação do SH3; não há valores para resumir.")
    approved_by_row = {
        int(item["row_index"]): _digits(str(item["account_code"]))
        for item in approvals
        if isinstance(item, dict) and "row_index" in item and "account_code" in item
    }
    reader = csv.DictReader(io.StringIO(_decode(inventory_data)), delimiter=";")
    columns = {_key(name.strip()): name for name in (reader.fieldnames or []) if name}
    account_column = columns.get("conta bem")
    value_column = columns.get("valor atual")
    plate_column = columns.get("plaqueta")
    asset_code_column = columns.get("codigo")
    description_column = columns.get("descricao")
    changed_items: list[dict[str, str]] = []
    if account_column and value_column:
        for row_index, row in enumerate(reader):
            new_code = approved_by_row.get(row_index)
            if not new_code:
                continue
            raw_old_account = (row.get(account_column) or "").strip()
            old_code = account_map.get(_digits(raw_old_account), "")
            new_account_code = account_map.get(new_code, "")
            if old_code == new_account_code:
                continue
            changed_items.append({
                "plate": (row.get(plate_column) or "").strip() if plate_column else "",
                "asset_code": (row.get(asset_code_column) or "").strip() if asset_code_column else "",
                "description": (row.get(description_column) or "").strip() if description_column else "",
                "old_code": old_code,
                "old_account": raw_old_account,
                "old_title": account_titles.get(old_code, "") if old_code else "Conta sem correspondência SH3",
                "new_code": new_account_code,
                "new_account": new_code,
                "new_title": account_titles.get(new_account_code, ""),
                "value": str(_money(row.get(value_column) or "")),
            })
    return _build_account_summary_xlsx(
        before_totals, after_totals, account_titles, excluded, changed_items
    ), len(excluded)


_ACCOUNT_LINE = re.compile(r"^\s*((?:\d+\.){2,}\d+)\s+(.+?)\s*$")
_AMOUNT = re.compile(r"-?\d[\d.]*,\d{2}")


def _read_ledger(data: bytes) -> tuple[dict[str, dict[str, str]], str]:
    text = _decode(data)
    totals: dict[str, dict[str, str]] = {}
    period = ""
    period_match = re.search(r"PER[IÍ]ODO:\s*(.+)", text, re.IGNORECASE)
    if period_match:
        period = period_match.group(1).strip()
    for line in text.splitlines():
        match = _ACCOUNT_LINE.match(line)
        if not match:
            continue
        code, remainder = match.groups()
        amounts = _AMOUNT.findall(remainder)
        if len(amounts) < 4:
            continue
        # Os quatro valores finais são: anterior, débito, crédito e saldo final.
        label = _AMOUNT.sub(" ", remainder).strip()
        totals[_digits(code)] = {
            "code": code,
            "title": re.sub(r"\s+", " ", label),
            "previous": _brl(_money(amounts[-4])),
            "debit": _brl(_money(amounts[-3])),
            "credit": _brl(_money(amounts[-2])),
            "balance": _brl(_money(amounts[-1])),
            "balance_value": str(_money(amounts[-1])),
        }
    if not totals:
        raise SpreadsheetError("Não encontrei linhas de contas no TXT. Confira se é o relatório PCASP de inventário ativo.")
    return totals, period


def analyze_files(inventory_data: bytes, ledger_data: bytes) -> dict:
    inventory, item_counts, item_total = _read_inventory(inventory_data)
    ledger, period = _read_ledger(ledger_data)
    rows = []
    matched = 0
    for code in sorted(set(inventory) | set(ledger)):
        inv_value = inventory.get(code)
        entry = ledger.get(code)
        if inv_value is not None and entry is not None:
            matched += 1
            balance = Decimal(entry["balance_value"])
            difference = inv_value - balance
            status = "Conferir diferença" if difference != 0 else "Valores iguais"
        elif inv_value is not None:
            balance = None
            difference = None
            status = "Conta do inventário não localizada no relatório"
        else:
            inv_value = None
            balance = Decimal(entry["balance_value"])
            difference = None
            status = "Conta do relatório sem bens vinculados por Conta Bem"
        rows.append({
            "code": entry["code"] if entry else _format_code(code),
            "title": entry["title"] if entry else "Conta presente no inventário",
            "item_count": item_counts.get(code, 0),
            "inventory_value": _brl(inv_value) if inv_value is not None else "—",
            "ledger_balance": _brl(balance) if balance is not None else "—",
            "difference": _brl(difference) if difference is not None else "—",
            "status": status,
            "has_difference": difference is not None and difference != 0,
        })
    rows.sort(key=lambda row: (not row["has_difference"], row["code"]))
    return {
        "period": period,
        "inventory_items": item_total,
        "inventory_accounts": len(inventory),
        "ledger_accounts": len(ledger),
        "matched_accounts": matched,
        "rows": rows,
        "note": "Comparação indicativa entre a soma de Valor Atual dos bens por Conta Bem e o Saldo Final do relatório. Diferenças podem decorrer de datas-base, critérios contábeis ou composição dos saldos; confira antes de concluir que há erro.",
    }
