"""Proves the offline guarantee: guarded document work cannot reach the network.

No real external connection is ever made — the guard raises *before* connecting,
so these tests are hermetic and fast.
"""
import socket
import threading

import pytest

from sanad_core import offline


def test_guard_blocks_non_loopback_egress():
    with offline.no_network():
        with pytest.raises(offline.NetworkEgressBlocked):
            socket.create_connection(("93.184.216.34", 80), timeout=0.5)  # example.com IP
        with pytest.raises(offline.NetworkEgressBlocked):
            s = socket.socket()
            try:
                s.connect(("8.8.8.8", 53))
            finally:
                s.close()


def test_guard_allows_loopback():
    # a local listener stands in for legitimate on-machine IPC
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    try:
        with offline.no_network():
            c = socket.create_connection(("127.0.0.1", port), timeout=1)  # must NOT raise
            c.close()
    finally:
        srv.close()


def test_block_is_scoped_and_restored():
    # outside the guard, egress attempts are not blocked by us (they fail/timeout
    # for ordinary reasons, never NetworkEgressBlocked)
    assert offline._blocked() is False
    with offline.no_network():
        assert offline._blocked() is True
    assert offline._blocked() is False


def test_block_is_thread_local():
    # a concurrent thread (e.g. the deliberately-online DOI lookup) is unaffected
    seen = {}
    def worker():
        seen["blocked"] = offline._blocked()
    with offline.no_network():
        t = threading.Thread(target=worker)
        t.start(); t.join()
    assert seen["blocked"] is False  # the other thread was never blocked
