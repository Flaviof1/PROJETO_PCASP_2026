"""Servidor HTTP local e rotas da aplicação."""

from __future__ import annotations

import json
import mimetypes
import threading
import webbrowser
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app.config import HOST, INITIAL_WORKBOOK, MAX_UPLOAD_BYTES, PORT, WEB_DIR
from app.pcasp import ensure_initial_data, get_status, import_workbook, search_accounts
from app.xlsx_reader import SpreadsheetError


class ApplicationHandler(BaseHTTPRequestHandler):
    server_version = "ConsultaPCASP/0.1"

    def _send(self, status: int, content: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'self'")
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
            self._json(200, get_status())
        elif parsed.path == "/api/search":
            params = parse_qs(parsed.query)
            query = params.get("q", [""])[0].strip()
            kind = params.get("tipo", [""])[0].strip()
            if len(query) > 160:
                self._json(400, {"error": "Use uma descrição de até 160 caracteres."})
                return
            self._json(200, {"results": search_accounts(query, kind) if query else []})
        elif parsed.path.startswith("/static/"):
            name = parsed.path.removeprefix("/static/")
            if name not in {"style.css", "app.js"}:
                self._json(404, {"error": "Arquivo não encontrado."})
                return
            self._static(name)
        else:
            self._json(404, {"error": "Rota não encontrada."})

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/upload":
            self._json(404, {"error": "Rota não encontrada."})
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
    url = f"http://{HOST}:{PORT}"
    print("Consulta PCASP iniciado neste computador.")
    print(f"Abra no navegador: {url}")
    print("Para encerrar, volte a esta janela e pressione Ctrl+C.")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAplicação encerrada.")
    finally:
        server.server_close()
