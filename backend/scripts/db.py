"""Embedded PostgreSQL 16 + pgvector via the `pgserver` wheel.

Usage:
  uv run python scripts/db.py start   # init (first run) + start on 127.0.0.1:PG_PORT, create database
  uv run python scripts/db.py stop
  uv run python scripts/db.py status
  uv run python scripts/db.py url     # print DATABASE_URL

The app itself only reads DATABASE_URL, so a hosted Postgres (Supabase, Homebrew,
Docker) can replace this script without code changes.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PGDATA = Path(os.environ.get("PGDATA_DIR", ROOT / ".pgdata")).resolve()
PORT = int(os.environ.get("PG_PORT", "54329"))
DB_NAME = os.environ.get("PG_DATABASE", "bhdh")
TEST_DB_NAME = os.environ.get("PG_TEST_DATABASE", "bhdh_test")
USER = "postgres"
# Unix socket dir must not contain spaces (the project path does); keep it in /tmp.
SOCKET_DIR = Path(os.environ.get("PG_SOCKET_DIR", f"/tmp/bhdh-pg-{PORT}"))


def _bin(name: str) -> str:
    import pgserver.postgres_server as ps

    return str(ps.POSTGRES_BIN_PATH / name)


def url(db: str = DB_NAME) -> str:
    return f"postgresql://{USER}@127.0.0.1:{PORT}/{db}"


def _run(args: list[str], check: bool = True, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=check, capture_output=True, text=True, **kw)


def is_running() -> bool:
    r = _run([_bin("pg_isready"), "-h", "127.0.0.1", "-p", str(PORT)], check=False)
    return r.returncode == 0


def _ensure_db(name: str) -> None:
    r = _run([_bin("psql"), url("postgres"), "-tAc", f"SELECT 1 FROM pg_database WHERE datname='{name}'"])
    if r.stdout.strip() != "1":
        _run([_bin("createdb"), "-h", "127.0.0.1", "-p", str(PORT), "-U", USER, name])
    _run([_bin("psql"), url(name), "-c", "CREATE EXTENSION IF NOT EXISTS vector"])


def start() -> None:
    if not (PGDATA / "PG_VERSION").exists():
        PGDATA.mkdir(parents=True, exist_ok=True)
        print(f"[db] initdb → {PGDATA}")
        _run([_bin("initdb"), "-D", str(PGDATA), "--auth=trust", "--encoding=utf8", "-U", USER])
    SOCKET_DIR.mkdir(parents=True, exist_ok=True)
    if is_running():
        print(f"[db] already running on 127.0.0.1:{PORT}")
    else:
        print(f"[db] starting on 127.0.0.1:{PORT}")
        _run([
            _bin("pg_ctl"), "-D", str(PGDATA), "-w", "-t", "30",
            "-o", f"-h 127.0.0.1 -p {PORT} -k '{SOCKET_DIR}'",
            "-l", str(PGDATA / "server.log"), "start",
        ])
        for _ in range(30):
            if is_running():
                break
            time.sleep(0.5)
    _ensure_db(DB_NAME)
    _ensure_db(TEST_DB_NAME)
    print(f"[db] ready. DATABASE_URL={url()}")


def stop() -> None:
    if not (PGDATA / "postmaster.pid").exists():
        print("[db] not running")
        return
    _run([_bin("pg_ctl"), "-D", str(PGDATA), "-w", "-m", "fast", "stop"], check=False)
    print("[db] stopped")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"
    if cmd == "start":
        start()
    elif cmd == "stop":
        stop()
    elif cmd == "status":
        print("running" if is_running() else "stopped")
        sys.exit(0 if is_running() else 1)
    elif cmd == "url":
        print(url())
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
