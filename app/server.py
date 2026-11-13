"""Servidor HTTP local e rotas da aplicação."""

from __future__ import annotations

import json
import mimetypes
import socket
import threading
import webbrowser
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app.config import HOST, INITIAL_WORKBOOK, MAX_UPLOAD_BYTES, PORT, WEB_DIR
from app.pcasp import delete_inventory_review_decisions, ensure_initial_data, get_status, import_workbook, search_accounts
from app.reconciliation import (
    analyze_files,
    export_account_summary,
    export_approved_changes,
    save_inventory_review_decision,
    suggest_inventory_reviews,
)
from app.xlsx_reader import SpreadsheetError


class ApplicationHandler(BaseHTTPRequestHandler):
    server_version = "ConsultaPCASP/0.1"

    def _send(self, status: int, content: bytes, content_type: str, extra_headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'self'")
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(content)

    def _json(self, status: int, payload: dict) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, content, "application/json; charset=utf-8")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._static("index.html")
        elif parsed.path == "/api/status":
            status = get_status()
            status["can_upload"] = self.client_address[0] in {"127.0.0.1", "::1"}
            self._json(200, status)
        elif parsed.path == "/api/search":
            params = parse_qs(parsed.query)
            query = params.get("q", [""])[0].strip()
            kind = params.get("tipo", [""])[0].strip()
            try:
                limit = min(50, max(1, int(params.get("limit", ["15"])[0])))
                offset = min(100000, max(0, int(params.get("offset", ["0"])[0])))
            except ValueError:
                self._json(400, {"error": "Parâmetros de paginação inválidos."})
                return
            if len(query) > 160:
                self._json(400, {"error": "Use uma descrição de até 160 caracteres."})
                return
            results = search_accounts(query, kind, limit=limit + 1, offset=offset) if query else []
            has_more = len(results) > limit
            self._json(200, {"results": results[:limit], "has_more": has_more, "offset": offset})
        elif parsed.path.startswith("/static/"):
            name = parsed.path.removeprefix("/static/")
            if name not in {"style.css", "app.js"}:
                self._json(404, {"error": "Arquivo não encontrado."})
                return
            self._static(name)
        else:
            self._json(404, {"error": "Rota não encontrada."})

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        if route not in {
            "/api/upload", "/api/reconcile", "/api/inventory-review",
            "/api/inventory-review-decision", "/api/inventory-review-decisions/clear",
            "/api/inventory-export", "/api/inventory-summary",
        }:
            self._json(404, {"error": "Rota não encontrada."})
            return
        if self.client_address[0] not in {"127.0.0.1", "::1"}:
            self._json(403, {"error": "Esta operação só pode ser feita no computador que hospeda o sistema."})
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_UPLOAD_BYTES:
            self._json(413, {"error": "Envie uma planilha de até 20 MB."})
            return
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().startswith("multipart/form-data;"):
            self._json(400, {"error": "Envie o arquivo pelo formulário de importação."})
            return
        body = self.rfile.read(length)
        envelope = (
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("ascii") + body
        )
        message = BytesParser(policy=policy.default).parsebytes(envelope)
        if route == "/api/inventory-review-decisions/clear":
            self._json(200, {"deleted": delete_inventory_review_decisions()})
            return
        if route == "/api/inventory-review-decision":
            parts = {}
            for part in message.iter_parts():
                if part.get_content_disposition() == "form-data":
                    name = part.get_param("name", header="content-disposition")
                    if name:
                        parts[name] = part
            decision = parts.get("decision")
            system_accounts = parts.get("plano_sh3")
            if decision is None or system_accounts is None or not system_accounts.get_filename():
                self._json(400, {"error": "Envie a decisão e a relação Localizar Plano de Contas.csv."})
                return
            try:
                save_inventory_review_decision(
                    decision.get_payload(decode=True) or b"",
                    system_accounts.get_payload(decode=True) or b"",
                )
                self._json(200, {"saved": True})
            except SpreadsheetError as exc:
                self._json(422, {"error": str(exc)})
            except Exception:
                self.log_error("Falha ao salvar decisão da revisão do inventário")
                self._json(500, {"error": "Não foi possível salvar a decisão da análise."})
            return
        if route == "/api/inventory-review":
            parts = {}
            for part in message.iter_parts():
                if part.get_content_disposition() == "form-data":
                    name = part.get_param("name", header="content-disposition")
                    if name:
                        parts[name] = part
            inventory = parts.get("inventario")
            system_accounts = parts.get("plano_sh3")
            if inventory is None or not inventory.get_filename():
                self._json(400, {"error": "Selecione o CSV Localizar Bens."})
                return
            if system_accounts is None or not system_accounts.get_filename():
                self._json(400, {"error": "Selecione Localizar Plano de Contas.csv para conferir as contas disponíveis no SH3."})
                return
            try:
                self._json(200, suggest_inventory_reviews(
                    inventory.get_payload(decode=True) or b"",
                    system_accounts.get_payload(decode=True) or b"",
                ))
            except SpreadsheetError as exc:
                self._json(422, {"error": str(exc)})
            except Exception:
                self.log_error("Falha ao gerar sugestões de revisão do inventário")
                self._json(500, {"error": "Não foi possível analisar o inventário."})
            return
        if route in {"/api/inventory-export", "/api/inventory-summary"}:
            parts = {}
            for part in message.iter_parts():
                if part.get_content_disposition() == "form-data":
                    name = part.get_param("name", header="content-disposition")
                    if name:
                        parts[name] = part
            inventory = parts.get("inventario")
            approvals = parts.get("aprovadas")
            system_accounts = parts.get("plano_sh3")
            if inventory is None or not inventory.get_filename() or approvals is None:
                self._json(400, {"error": "Envie o CSV original e as aprovações da revisão."})
                return
            if system_accounts is None or not system_accounts.get_filename():
                self._json(400, {"error": "Selecione Localizar Plano de Contas.csv para relacionar os códigos do SH3."})
                return
            try:
                inventory_data = inventory.get_payload(decode=True) or b""
                approvals_data = approvals.get_payload(decode=True) or b""
                extra_headers = None
                if route == "/api/inventory-summary":
                    result, excluded_count = export_account_summary(
                        inventory_data,
                        approvals_data,
                        system_accounts.get_payload(decode=True) or b"",
                    )
                    extra_headers = {"X-Summary-Excluded": str(excluded_count)}
                else:
                    result = export_approved_changes(
                        inventory_data,
                        approvals_data,
                        system_accounts.get_payload(decode=True) or b"",
                    )
                content_type = (
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    if route == "/api/inventory-summary"
                    else "text/csv; charset=windows-1252"
                )
                self._send(200, result, content_type, extra_headers)
            except SpreadsheetError as exc:
                self._json(422, {"error": str(exc)})
            except Exception:
                self.log_error("Falha ao exportar arquivo da revisão do inventário")
                error = "Não foi possível gerar o resumo por conta." if route == "/api/inventory-summary" else "Não foi possível criar a cópia com as alterações aprovadas."
                self._json(500, {"error": error})
            return
        if route == "/api/reconcile":
            files = {}
            for part in message.iter_parts():
                if part.get_content_disposition() != "form-data":
                    continue
                field_name = part.get_param("name", header="content-disposition")
                if field_name in {"inventario", "relatorio"} and part.get_filename():
                    files[field_name] = part.get_payload(decode=True) or b""
            if not files.get("inventario") or not files.get("relatorio"):
                self._json(400, {"error": "Selecione o CSV do inventário e o TXT do relatório PCASP."})
                return
            try:
                self._json(200, analyze_files(files["inventario"], files["relatorio"]))
            except SpreadsheetError as exc:
                self._json(422, {"error": str(exc)})
            except Exception:
                self.log_error("Falha ao analisar os relatórios")
                self._json(500, {"error": "Não foi possível analisar os arquivos selecionados."})
            return
        upload = next(
            (part for part in message.iter_parts()
             if part.get_content_disposition() == "form-data" and part.get_param("name", header="content-disposition") == "arquivo"),
            None,
        )
        if upload is None:
            self._json(400, {"error": "Selecione a planilha Excel para importar."})
            return
        filename = Path(upload.get_filename() or "planilha.xlsx").name
        if Path(filename).suffix.casefold() != ".xlsx":
            self._json(400, {"error": "Por enquanto, aceito planilhas .xlsx."})
            return
        try:
            count = import_workbook(upload.get_payload(decode=True) or b"", filename)
        except SpreadsheetError as exc:
            self._json(422, {"error": str(exc)})
            return
        except Exception:
            self.log_error("Falha ao importar a planilha")
            self._json(500, {"error": "Não foi possível importar a planilha. Confira se ela está fechada e tente novamente."})
            return
        self._json(200, {"message": f"Importação concluída: {count:,} contas carregadas.", "account_count": count})

    def _static(self, filename: str) -> None:
        path = WEB_DIR / filename
        if not path.is_file():
            self._json(404, {"error": "Arquivo não encontrado."})
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        charset = "; charset=utf-8" if content_type.startswith(("text/", "application/javascript")) else ""
        self._send(200, path.read_bytes(), content_type + charset)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")


def main() -> None:
    ensure_initial_data(INITIAL_WORKBOOK)
    server = ThreadingHTTPServer((HOST, PORT), ApplicationHandler)
    local_url = f"http://127.0.0.1:{PORT}"
    print("Consulta PCASP iniciado neste computador.")
    print(f"Neste computador: {local_url}")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 80))
            lan_ip = probe.getsockname()[0]
        if lan_ip and not lan_ip.startswith("127."):
            print(f"Outros computadores da mesma rede: http://{lan_ip}:{PORT}")
    except OSError:
        print("Não consegui identificar o IP da rede. Consulte o IPv4 com o comando ipconfig.")
    print("Para encerrar, volte a esta janela e pressione Ctrl+C.")
    threading.Timer(0.8, lambda: webbrowser.open(local_url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAplicação encerrada.")
    finally:
        server.server_close()
