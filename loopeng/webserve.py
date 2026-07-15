from __future__ import annotations

import http.server
import errno
import secrets
import socket
import ssl
import subprocess
import threading
from pathlib import Path
from urllib.parse import unquote, urlsplit

from ._paths import agent_root

DEFAULT_PORT = 8443


def external_ip() -> str:
    """Return the address selected by the host's default IPv4 route.

    UDP connect does not send application data; it asks the kernel which local
    interface would be used for an external destination.  This avoids
    advertising loopback while keeping the server bound to one concrete
    interface instead of the unsafe wildcard address.
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        address = probe.getsockname()[0]
    except OSError:
        address = ""
    finally:
        probe.close()
    if not address or address.startswith("127."):
        raise RuntimeError("could not determine a non-loopback host IP; refusing to advertise or bind 127.0.0.1")
    return address


class _Handler(http.server.BaseHTTPRequestHandler):
    server_version = "loopeng-https/1"

    def log_message(self, *_args: object) -> None:
        return

    def do_GET(self) -> None:
        server = self.server
        path = unquote(urlsplit(self.path).path)
        prefix = "/" + server.access_token
        if path == prefix:
            path += "/index.html"
        if not path.startswith(prefix + "/"):
            self.send_error(404)
            return
        relative = path[len(prefix) + 1:]
        if not relative or relative.endswith("/"):
            relative += "index.html"
        candidate = (server.out_root / relative).resolve()
        try:
            candidate.relative_to(server.out_root.resolve())
        except ValueError:
            self.send_error(404)
            return
        if candidate.is_dir() or not candidate.is_file():
            self.send_error(404)
            return
        try:
            data = candidate.read_bytes()
        except OSError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml" if candidate.suffix == ".svg" else "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class WebServer:
    def __init__(self, repo: Path, port: int = DEFAULT_PORT) -> None:
        self.repo = repo.resolve()
        self.out_root = self.repo / "_out"
        self.access_token = secrets.token_urlsafe(16)
        self.host = external_ip()
        self.port = port
        self.httpd: http.server.ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        return f"https://{self.host}:{self.port}/{self.access_token}/"

    def _certificate(self) -> tuple[Path, Path]:
        root = self.repo / agent_root("state", "tls")
        root.mkdir(parents=True, exist_ok=True)
        cert, key = root / "cert.pem", root / "key.pem"
        if cert.is_file() and key.is_file():
            return cert, key
        command = ["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes", "-keyout", str(key), "-out", str(cert), "-days", "825", "-subj", "/CN=loopeng-local"]
        try:
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        except FileNotFoundError as exc:
            raise RuntimeError("openssl is required to create the HTTPS certificate; refusing plaintext HTTP") from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"openssl failed to create HTTPS certificate: {exc.stderr.strip()}") from exc
        return cert, key

    def start(self, background: bool = True) -> "WebServer":
        self.out_root.mkdir(parents=True, exist_ok=True)
        cert, key = self._certificate()
        try:
            httpd = http.server.ThreadingHTTPServer((self.host, self.port), _Handler)
        except OSError as exc:
            if self.port != 0 and getattr(exc, "errno", None) in {errno.EADDRINUSE, 48, 10048}:
                httpd = http.server.ThreadingHTTPServer((self.host, 0), _Handler)
            else:
                raise
        httpd.access_token = self.access_token
        httpd.out_root = self.out_root
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(certfile=cert, keyfile=key)
        httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
        self.httpd = httpd
        self.port = int(httpd.server_address[1])
        if background:
            self.thread = threading.Thread(target=httpd.serve_forever, name="loopeng-https", daemon=True)
            self.thread.start()
        else:
            httpd.serve_forever()
        return self

    def stop(self) -> None:
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None


def serve(repo: Path, port: int = DEFAULT_PORT) -> WebServer:
    server = WebServer(repo, port)
    return server.start(background=True)
