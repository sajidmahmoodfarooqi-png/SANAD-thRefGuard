"""Hard offline guarantee for document processing.

An academic red line: a thesis that goes through SANAD's formatting routine must
never leave the machine. If it did — uploaded to any service, cached, indexed —
a plagiarism checker could later match the student's *own* work against that
online copy and flag it. So document handling must be provably local.

`no_network()` is the enforcement. Inside it, any attempt to open a socket to a
*non-loopback* address raises `NetworkEgressBlocked` instead of connecting — so
if any code in a guarded path ever tried to send the document out, it fails
loudly rather than silently succeeding. Loopback (127.0.0.1 / ::1) stays allowed:
it never leaves the machine and can't create a web footprint.

The block is thread-local: only the thread doing document work is restricted, so
it can't interfere with an unrelated, deliberately-online action (the opt-in DOI
lookup) running concurrently in the local Core. The document-formatting handler
runs inside this guard, and a guarantee test proves the routine completes with
zero egress.
"""
from __future__ import annotations

import ipaddress
import socket
import threading
from contextlib import contextmanager


class NetworkEgressBlocked(RuntimeError):
    """Raised when guarded code tries to reach a non-loopback address."""


_state = threading.local()
_orig_connect = socket.socket.connect
_orig_connect_ex = socket.socket.connect_ex
_orig_create_connection = socket.create_connection
_installed = False


def _blocked() -> bool:
    return getattr(_state, "blocked", False)


def _is_loopback(address) -> bool:
    try:
        host = address[0] if isinstance(address, (tuple, list)) else address
        return ipaddress.ip_address(socket.gethostbyname(str(host))).is_loopback
    except Exception:
        return False  # can't resolve to a loopback IP -> treat as egress, block it


def _check(address):
    if _blocked() and not _is_loopback(address):
        raise NetworkEgressBlocked(
            f"network egress blocked during a document-only operation "
            f"(attempted connection to {address!r}); the document never leaves this machine")


def _guarded_connect(self, address):
    _check(address)
    return _orig_connect(self, address)


def _guarded_connect_ex(self, address):
    _check(address)
    return _orig_connect_ex(self, address)


def _guarded_create_connection(address, *args, **kwargs):
    _check(address)
    return _orig_create_connection(address, *args, **kwargs)


def install() -> None:
    """Patch the socket layer once (idempotent). A no-op until a thread actually
    enters no_network(), so it never affects normal operation."""
    global _installed
    if _installed:
        return
    socket.socket.connect = _guarded_connect
    socket.socket.connect_ex = _guarded_connect_ex
    socket.create_connection = _guarded_create_connection
    _installed = True


@contextmanager
def no_network():
    """Within this block (current thread only), any connection to a non-loopback
    address raises NetworkEgressBlocked. Wrap document-processing code in it."""
    install()
    prev = getattr(_state, "blocked", False)
    _state.blocked = True
    try:
        yield
    finally:
        _state.blocked = prev
