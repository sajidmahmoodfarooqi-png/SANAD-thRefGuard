import pytest
from fastapi.testclient import TestClient

from sanad_core.server import create_app

# A tiny, deterministic invented library: a 1-author book and a 2-author DOI article.
SAMPLE_RIS = """TY  - BOOK
AU  - Fisher, R. K.
TI  - The Art of Memory
PY  - 2001
PB  - Chandler Press
ER  -
TY  - JOUR
AU  - Nguyen, Linh
AU  - Ortega, Pablo M.
TI  - A framework for distributed caching
T2  - Journal of Systems Engineering
PY  - 2016
VL  - 262
SP  - 101
EP  - 111
DO  - 10.1234/jse.2016.014
ER  -
"""


@pytest.fixture
def client(tmp_path):
    # a real temp-file DB so state persists across requests (":memory:" would
    # not -- each connection would see a fresh empty database)
    app = create_app(tmp_path / "sanad_test.db")
    c = TestClient(app)
    c.headers.update({"Authorization": f"Bearer {app.state.token}"})
    c.sanad_token = app.state.token  # for WebSocket query-param auth
    return c


@pytest.fixture
def seeded(client):
    r = client.post("/v1/library/import", json={"format": "ris", "text": SAMPLE_RIS})
    assert r.status_code == 200
    assert r.json()["imported"] == 2
    return client


def _ref_id(client, query):
    res = client.get("/v1/library/search", params={"q": query}).json()["results"]
    assert res, f"no library result for {query!r}"
    return res[0]["id"]


# --------------------------------------------------------------------------- #

def test_health(client):
    r = client.get("/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "sanad-core"
    assert body["version"]
    assert "db_path" not in body  # never leak the library path on the open probe


# -- security --------------------------------------------------------------- #

def test_protected_endpoints_require_token(tmp_path):
    app = create_app(tmp_path / "auth.db")
    raw = TestClient(app)  # no Authorization header
    assert raw.get("/v1/health").status_code == 200          # liveness is open
    assert raw.get("/v1/library/search").status_code == 401   # everything else isn't
    assert raw.post("/v1/library/import",
                    json={"format": "ris", "text": "x"}).status_code == 401


def test_wrong_token_is_rejected(tmp_path):
    app = create_app(tmp_path / "auth2.db")
    c = TestClient(app)
    c.headers.update({"Authorization": "Bearer not-the-token"})
    assert c.get("/v1/library/search").status_code == 401


def test_foreign_host_header_is_rejected(client):
    # DNS-rebinding defence: a Host the Core doesn't own is refused outright
    r = client.get("/v1/health", headers={"host": "evil.example.com"})
    assert r.status_code == 400


def test_websocket_requires_token(client):
    import pytest as _pytest
    from starlette.websockets import WebSocketDisconnect
    with _pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/v1/events") as ws:  # no ?token=
            ws.receive_json()


def test_import_too_large_is_413(seeded):
    huge = "TY  - BOOK\n" + ("x" * 8_000_001)
    r = seeded.post("/v1/library/import", json={"format": "ris", "text": huge})
    assert r.status_code == 413


def test_import_and_search(seeded):
    res = seeded.get("/v1/library/search", params={"q": "Fisher"}).json()["results"]
    assert len(res) == 1
    assert "Art of Memory" in res[0]["title"]
    assert res[0]["year"] == 2001


def test_search_by_author_surname(seeded):
    res = seeded.get("/v1/library/search", params={"q": "Ortega"}).json()["results"]
    assert any("distributed caching" in r["title"] for r in res)


def test_import_unknown_format_is_400(client):
    r = client.post("/v1/library/import", json={"format": "csv", "text": "x"})
    assert r.status_code == 400


def test_create_single_author_citation(seeded):
    rid = _ref_id(seeded, "Fisher")
    r = seeded.post("/v1/citations", json={"document_id": "doc1", "reference_ids": [rid]})
    assert r.status_code == 200
    body = r.json()
    assert body["citation_id"]
    assert body["rendered_text"] == "(Fisher, 2001)"


def test_create_two_author_citation(seeded):
    rid = _ref_id(seeded, "distributed caching")
    r = seeded.post("/v1/citations", json={"document_id": "doc1", "reference_ids": [rid]})
    assert r.json()["rendered_text"] == "(Nguyen & Ortega, 2016)"


def test_grouped_citation_sorts_alphabetically(seeded):
    fisher = _ref_id(seeded, "Fisher")
    nguyen = _ref_id(seeded, "distributed caching")
    r = seeded.post("/v1/citations",
                    json={"document_id": "doc1", "reference_ids": [fisher, nguyen]})
    # APA orders a grouped citation alphabetically: Fisher before Nguyen
    assert r.json()["rendered_text"] == "(Fisher, 2001; Nguyen & Ortega, 2016)"


def test_create_citation_empty_refs_is_400(seeded):
    r = seeded.post("/v1/citations", json={"document_id": "doc1", "reference_ids": []})
    assert r.status_code == 400


def test_update_citation_swaps_reference(seeded):
    fisher = _ref_id(seeded, "Fisher")
    nguyen = _ref_id(seeded, "distributed caching")
    cid = seeded.post("/v1/citations",
                      json={"document_id": "doc1", "reference_ids": [fisher]}).json()["citation_id"]
    r = seeded.put(f"/v1/citations/{cid}", json={"reference_ids": [nguyen]})
    assert r.status_code == 200
    assert r.json()["rendered_text"] == "(Nguyen & Ortega, 2016)"


def test_update_nonexistent_citation_is_404(seeded):
    r = seeded.put("/v1/citations/does-not-exist", json={"reference_ids": []})
    assert r.status_code == 404


def test_bibliography_reflects_cited_works(seeded):
    fisher = _ref_id(seeded, "Fisher")
    seeded.post("/v1/citations", json={"document_id": "docB", "reference_ids": [fisher]})
    entries = seeded.get("/v1/documents/docB/bibliography").json()["entries"]
    assert len(entries) == 1
    assert entries[0].startswith("Fisher, R. K. (2001).")
    assert ".." not in entries[0]  # cleanup net still applied through the API


def test_bibliography_empty_for_unknown_document(seeded):
    assert seeded.get("/v1/documents/never-cited/bibliography").json()["entries"] == []


# -- style profiles --------------------------------------------------------- #

def _make_profile(**overrides):
    return {
        "name": "Test Profile", "based_on_csl": "apa",
        "csl_overrides": overrides, "paragraph_style": {},
        "document_structure": {"enabled": False},
        "provenance": {"confirmed_by_user": True},
    }


def test_style_profile_create_and_apply_changes_rendering(seeded):
    # baseline: ampersand
    nguyen = _ref_id(seeded, "distributed caching")
    seeded.post("/v1/citations", json={"document_id": "docS", "reference_ids": [nguyen]})
    base = seeded.get("/v1/documents/docS/bibliography").json()["entries"][0]
    assert " & Ortega" in base

    # create + apply an ampersand->text override profile
    pid = seeded.post("/v1/style-profiles",
                      json=_make_profile(ampersand_in_bibliography=False,
                                         ampersand_in_text=False)).json()["id"]
    r = seeded.post(f"/v1/style-profiles/{pid}/apply", json={"document_id": "docS"})
    assert r.status_code == 200
    assert r.json()["rerendered_citations"] == 1
    after = r.json()["bibliography"][0]
    assert " and Ortega" in after and " & Ortega" not in after


def test_apply_nonexistent_profile_is_404(seeded):
    r = seeded.post("/v1/style-profiles/nope/apply", json={"document_id": "docS"})
    assert r.status_code == 404


def test_invalid_style_profile_is_422(seeded):
    bad = _make_profile()
    bad["based_on_csl"] = "not-a-real-style"
    r = seeded.post("/v1/style-profiles", json=bad)
    assert r.status_code == 422


# -- Sprint 6: guided build, list, get, paragraph_style --------------------- #

def test_build_style_profile_endpoint(client):
    r = client.post("/v1/style-profiles/build", json={
        "name": "Metropolitan Thesis 2026", "university": "Metropolitan University",
        "hanging_indent_cm": 1.27, "font_family": "Times New Roman",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["id"]
    assert body["profile"]["name"] == "Metropolitan Thesis 2026"
    assert body["profile"]["paragraph_style"]["bibliography_hanging_indent_cm"] == 1.27

    got = client.get(f"/v1/style-profiles/{body['id']}").json()
    assert got["based_on_csl"] == "apa"
    assert got["university"] == "Metropolitan University"


def test_build_invalid_style_profile_is_422(client):
    r = client.post("/v1/style-profiles/build", json={"based_on_csl": "not-real"})
    assert r.status_code == 422


def test_list_and_get_style_profiles(client):
    pid = client.post("/v1/style-profiles/build", json={"name": "Only One"}).json()["id"]
    listing = client.get("/v1/style-profiles").json()["profiles"]
    assert any(p["id"] == pid and p["name"] == "Only One" for p in listing)
    assert client.get("/v1/style-profiles/does-not-exist").status_code == 404


def test_bibliography_carries_office_paragraph_style(seeded):
    rid = _ref_id(seeded, "Fisher")
    seeded.post("/v1/citations", json={"document_id": "docP", "reference_ids": [rid]})
    body = seeded.get("/v1/documents/docP/bibliography").json()
    assert body["entries"]
    # the default profile yields a real hanging indent for the add-in to apply
    ps = body["paragraph_style"]
    assert ps["leftIndentPt"] == 36.0 and ps["firstLineIndentPt"] == -36.0
    assert ps["fontName"] == "Times New Roman"


def test_built_profile_applied_changes_rendering_and_keeps_style(seeded):
    # a guided-built ampersand->text profile, applied, reaches real output
    nguyen = _ref_id(seeded, "distributed caching")
    seeded.post("/v1/citations", json={"document_id": "docBuilt", "reference_ids": [nguyen]})
    pid = seeded.post("/v1/style-profiles/build", json={
        "name": "No-Ampersand", "ampersand_in_text": False,
        "ampersand_in_bibliography": False,
    }).json()["id"]
    seeded.post(f"/v1/style-profiles/{pid}/apply", json={"document_id": "docBuilt"})
    body = seeded.get("/v1/documents/docBuilt/bibliography").json()
    assert " and Ortega" in body["entries"][0]
    assert body["paragraph_style"]["fontName"]  # style still travels with content


# -- integrity scan (Tier-A engine, live) ----------------------------------- #

def test_scan_clean_document_has_no_flags(seeded):
    rid = _ref_id(seeded, "Fisher")
    seeded.post("/v1/citations",
                json={"document_id": "docClean", "reference_ids": [rid],
                      "raw_original_text": "(Fisher, 2001)"})
    r = seeded.post("/v1/documents/docClean/scan")
    assert r.status_code == 200
    body = r.json()
    assert body["flags"] == []
    # no citing sentences sent -> Tier-B honestly reports it did not run
    assert body["tier_b"]["ran"] is False
    assert body["tier_b"]["backend"] is None


def test_scan_detects_year_mismatch(seeded):
    rid = _ref_id(seeded, "Fisher")  # library year 2001
    seeded.post("/v1/citations",
                json={"document_id": "docY", "reference_ids": [rid],
                      "raw_original_text": "(Fisher, 1998)"})
    body = seeded.post("/v1/documents/docY/scan").json()
    rules = {f["rule_id"] for f in body["flags"]}
    assert "R1_YEAR_MISMATCH" in rules
    assert body["open_count"] >= 1


def test_flags_listing_and_dismiss_flow(seeded):
    rid = _ref_id(seeded, "Fisher")
    seeded.post("/v1/citations",
                json={"document_id": "docF", "reference_ids": [rid],
                      "raw_original_text": "(Fisher, 1998)"})
    seeded.post("/v1/documents/docF/scan")

    flags = seeded.get("/v1/documents/docF/flags").json()["flags"]
    fid = flags[0]["id"]

    r = seeded.put(f"/v1/flags/{fid}", json={"status": "dismissed"})
    assert r.status_code == 200

    # re-scan must not resurrect the dismissed flag as a new open one
    after = seeded.post("/v1/documents/docF/scan").json()
    assert after["open_count"] == 0


def test_scan_with_contexts_runs_tier_b(client):
    # an oceanography source + a finance source, both with abstracts
    ris = """TY  - JOUR
AU  - Marsh, E.
TI  - Tides and the lunar cycle
AB  - Coastal water levels rise and fall with the moon's gravitational pull across the lunar month.
PY  - 2015
ER  -
TY  - JOUR
AU  - Frost, D.
TI  - Consumer credit and interest rates
AB  - Central bank interest rate decisions affect inflation and lending in the commercial banking sector.
PY  - 2018
ER  -
"""
    client.post("/v1/library/import", json={"format": "ris", "text": ris})
    finance = _ref_id(client, "Consumer credit")
    cid = client.post("/v1/citations",
                      json={"document_id": "docCtx", "reference_ids": [finance],
                            "raw_original_text": "(Frost, 2018)"}).json()["citation_id"]

    body = client.post("/v1/documents/docCtx/scan", json={
        "contexts": {cid: "The rise and fall of coastal water levels follows the "
                          "moon's gravitational pull across the month."}}).json()
    assert body["tier_b"]["ran"] is True
    assert body["tier_b"]["backend"]  # names whichever backend actually ran
    assert any(f["rule_id"] == "R8_CONTEXT_MISALIGNMENT" for f in body["flags"])


def test_flag_update_unknown_is_404(seeded):
    r = seeded.put("/v1/flags/nope", json={"status": "confirmed"})
    assert r.status_code == 404


def test_flag_update_bad_status_is_422(seeded):
    r = seeded.put("/v1/flags/whatever", json={"status": "banana"})
    assert r.status_code == 422


# -- honest stubs for later-sprint endpoints -------------------------------- #

def test_handbook_parse_is_501(seeded):
    r = seeded.post("/v1/handbook/parse")
    assert r.status_code == 501


# -- websocket -------------------------------------------------------------- #

def test_events_websocket_connect_and_ping(client):
    with client.websocket_connect(f"/v1/events?token={client.sanad_token}") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "connected"
        ws.send_text("ping")
        pong = ws.receive_json()
        assert pong["type"] == "pong"
        assert pong["echo"] == "ping"


# -- event hub (scan broadcasts) -------------------------------------------- #

class _FakeWS:
    """Minimal stand-in for a Starlette WebSocket: records what it was sent,
    or raises to simulate a dropped client."""

    def __init__(self, broken=False):
        self.sent = []
        self.broken = broken

    async def send_json(self, data):
        if self.broken:
            raise RuntimeError("client gone")
        self.sent.append(data)


def test_event_hub_broadcasts_and_drops_dead_clients():
    import asyncio

    from sanad_core.server import EventHub

    async def scenario():
        hub = EventHub()
        live, dead = _FakeWS(), _FakeWS(broken=True)
        hub.register(live)
        hub.register(dead)

        await hub.broadcast({"type": "scan-complete", "flag_count": 3})
        assert live.sent == [{"type": "scan-complete", "flag_count": 3}]

        # the broken client is discarded so it can't break future broadcasts
        await hub.broadcast({"type": "ping-again"})
        assert len(live.sent) == 2

    asyncio.run(scenario())
