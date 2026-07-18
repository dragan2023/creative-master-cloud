#!/usr/bin/env python3
"""Own an isolated E2E backend and run document concurrency verification."""

from __future__ import annotations

from collections import deque
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time

import httpx


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
PYTHON = BACKEND / "venv" / "Scripts" / "python.exe"
SERVER = BACKEND / "scripts" / "run_e2e_server.py"
VERIFIER = ROOT / "scripts" / "verify_document_concurrency.py"
BASE_URL = "http://127.0.0.1:8002"
RAW_REPORT = ROOT / "artifacts" / "document_concurrency_raw.json"
MARKDOWN_REPORT = ROOT / "artifacts" / "document_concurrency_summary.md"


def _port_open(port: int) -> bool:
    with socket.socket() as connection:
        connection.settimeout(0.5)
        return connection.connect_ex(("127.0.0.1", port)) == 0


def _drain(stream, tail: deque[str]) -> None:
    for line in iter(stream.readline, ""):
        tail.append(line.rstrip())


def _wait_for_server(process: subprocess.Popen, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"E2E backend exited during startup: {process.returncode}")
        try:
            response = httpx.get(f"{BASE_URL}/api/v1/health", timeout=1.0)
            if 200 <= response.status_code < 300:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    raise TimeoutError("E2E backend health check timed out")


def _acquire_token() -> str:
    credentials = {
        "username": "qa_doc_concurrency",
        "email": "qa-doc-concurrency@example.com",
        "password": "qa-doc-concurrency-local-0001",
    }
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": credentials["username"], "password": credentials["password"]},
        )
        if not 200 <= response.status_code < 300:
            response = client.post("/api/v1/auth/register", json=credentials)
        if not 200 <= response.status_code < 300:
            raise RuntimeError(
                f"temporary test authentication failed: HTTP {response.status_code} "
                f"{response.text[:500]}"
            )
        token = ((response.json().get("data") or {}).get("access_token"))
        if not token:
            raise RuntimeError("authentication response omitted access_token")
        return token


def _shutdown(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.stdin.write("shutdown\n")
        process.stdin.flush()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired as error:
            process.terminate()
            process.wait(timeout=10)
            raise RuntimeError("E2E backend ignored cooperative stdin shutdown") from error
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and _port_open(8002):
        time.sleep(0.1)
    if _port_open(8002):
        raise RuntimeError("E2E backend port 8002 remained open after shutdown")
    if process.returncode != 0:
        raise RuntimeError(f"E2E backend shutdown returned {process.returncode}")


def main() -> int:
    if _port_open(8002):
        print("ERROR: port 8002 is already occupied; refusing to reuse it", file=sys.stderr)
        return 2
    server_tail: deque[str] = deque(maxlen=120)
    server = None
    verifier_code = 1
    cleanup_error = None
    with tempfile.TemporaryDirectory(prefix="document-concurrency-e2e-") as temporary:
        temporary_root = Path(temporary)
        environment = os.environ.copy()
        environment.update(
            {
                "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8",
                "RUNTIME_ENV": "test",
                "E2E_BACKEND_PORT": "8002",
                "QA_TEST_HOOKS": "0",
                "DATABASE_URL": f"sqlite+aiosqlite:///{(temporary_root / 'app.db').as_posix()}",
                "REDIS_URL": "memory://",
                "SECRET_KEY": "document-concurrency-e2e-secret-key-only",
                "CHROMA_PERSIST_DIR": str(temporary_root / "chroma"),
                "CHROMA_MODEL_CACHE_DIR": str(BACKEND / "data" / "chroma" / "models"),
                "KNOWLEDGE_GRAPH_DIR": str(temporary_root / "knowledge-graphs"),
                "UPLOAD_DIR": str(temporary_root / "uploads"),
                "DOC_PREPROCESSOR_ENABLED": "false",
                "USE_GPU": "false",
            }
        )
        try:
            server = subprocess.Popen(
                [str(PYTHON), str(SERVER)],
                cwd=BACKEND,
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            threads = [
                threading.Thread(target=_drain, args=(server.stdout, server_tail), daemon=True),
                threading.Thread(target=_drain, args=(server.stderr, server_tail), daemon=True),
            ]
            for thread in threads:
                thread.start()
            _wait_for_server(server)
            token = _acquire_token()
            verifier_environment = environment.copy()
            verifier_environment["DOCUMENT_VERIFY_TOKEN"] = token
            verifier_environment["DOCUMENT_VERIFY_BASE_URL"] = BASE_URL
            verifier = subprocess.run(
                [
                    str(PYTHON),
                    str(VERIFIER),
                    "--json-output",
                    str(RAW_REPORT),
                    "--markdown-output",
                    str(MARKDOWN_REPORT),
                    "--scale",
                    "2",
                    "--processing-timeout",
                    "600",
                    "--request-timeout",
                    "30",
                ],
                cwd=ROOT,
                env=verifier_environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=1500,
            )
            verifier_code = verifier.returncode
            print(f"verifier exit code: {verifier_code}")
            if verifier_code and verifier.stderr:
                safe_error = verifier.stderr.encode("ascii", "backslashreplace").decode("ascii")
                print(safe_error.strip(), file=sys.stderr)
        except Exception as error:
            print(f"ERROR: {type(error).__name__}: {error}", file=sys.stderr)
            verifier_code = 1
        finally:
            if server is not None:
                try:
                    _shutdown(server)
                except Exception as error:
                    cleanup_error = error
                    print(f"ERROR: {type(error).__name__}: {error}", file=sys.stderr)

    if verifier_code and server_tail:
        print("E2E backend tail:", file=sys.stderr)
        for line in server_tail:
            print(line, file=sys.stderr)
    if RAW_REPORT.exists():
        report = json.loads(RAW_REPORT.read_text(encoding="utf-8"))
        if any("token" in key.lower() for key in report):
            print("ERROR: raw report contains a token-like top-level key", file=sys.stderr)
            return 1
    return 1 if cleanup_error else verifier_code


if __name__ == "__main__":
    raise SystemExit(main())
