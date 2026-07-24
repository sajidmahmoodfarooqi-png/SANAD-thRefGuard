"""Frozen entry point for the SANAD Core service (PyInstaller target).

Builds to a standalone `sanad-core` executable so the packaged desktop app needs
no system Python. The desktop shell launches this and talks to it over HTTP, the
same as it does the `python -m sanad_core.server` sidecar in development.

Config via environment (the shell sets these):
  SANAD_DB    path to the SQLite library file (default: sanad_library.db in cwd)
  SANAD_PORT  port to bind on 127.0.0.1 (default: 23890)
"""
import os
import sys


def main() -> int:
    from sanad_core import server

    db = os.environ.get("SANAD_DB", "sanad_library.db")
    port = int(os.environ.get("SANAD_PORT", server.DEFAULT_PORT))
    server.serve(db_path=db, host=server.DEFAULT_HOST, port=port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
