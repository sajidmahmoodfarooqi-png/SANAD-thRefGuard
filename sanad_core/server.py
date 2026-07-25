"""SANAD Core local HTTP + WebSocket service (MVP_SPEC.md §3).

A thin FastAPI wrapper over the `documents` / `style_profile` / `importer`
service layers. Binds only to 127.0.0.1 -- it is a local companion for the
word-processor add-in, never a network service. The add-in talks to this;
it never touches the SQLite library directly.

Endpoints that depend on later sprints are honest stubs rather than fake
results:
  * POST /v1/documents/{id}/scan   -> Tier-A engine, LIVE (Sprint 5). The
                                      Tier-B semantic check (R8) is still pending.
  * POST /v1/handbook/parse        -> handbook parsing (v1.x)  -> HTTP 501
"""
from __future__ import annotations

import base64
import os
import secrets
import stat
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from . import __version__, db, documents, embedding, importer, integrity, list_import, resolver
from . import style_profile as sp

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 23890
# an import body larger than this is refused (memory-exhaustion guard). 8 MB of
# RIS/BibTeX is tens of thousands of references -- far beyond any real paste.
MAX_IMPORT_CHARS = 8_000_000


# --------------------------------------------------------------------------- #
# request/response models
# --------------------------------------------------------------------------- #

class CitationCreate(BaseModel):
    document_id: str
    reference_ids: list[str]
    raw_original_text: str | None = None


class CitationUpdate(BaseModel):
    reference_ids: list[str] | None = None


class StyleProfileApply(BaseModel):
    document_id: str


class ImportRequest(BaseModel):
    format: str            # ris | bibtex | typed | csv | xlsx | docx
    text: str = ""         # text formats (ris/bibtex/typed/csv)
    data_b64: str | None = None  # base64 file bytes for binary formats (xlsx/docx)
    resolve: bool = False        # opt-in Crossref DOI lookup (off by default)


class ScanRequest(BaseModel):
    # all optional: the add-in supplies these from the live document when it
    # can, but a bare `POST /scan` (DB-only reconciliation) is valid too.
    present_control_ids: list[str] | None = None   # feeds R3 orphan-control check
    listed_reference_ids: list[str] | None = None  # feeds R5 listed-not-cited
    contexts: dict[str, str] | None = None         # citation_id -> citing sentence
                                                   # (Tier-B R8); read live, never stored


class FlagStatusUpdate(BaseModel):
    status: str  # open | confirmed | dismissed


# --------------------------------------------------------------------------- #
# event hub: server -> add-in push channel over /v1/events
# --------------------------------------------------------------------------- #

class EventHub:
    """Fan-out of scan/library events to every connected WebSocket client. In
    process, single machine -- no broker needed. A send that fails just drops
    that client rather than breaking the broadcast for everyone."""

    def __init__(self):
        self._clients: set[WebSocket] = set()

    def register(self, ws: WebSocket) -> None:
        self._clients.add(ws)

    def unregister(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def broadcast(self, event: dict) -> None:
        for ws in list(self._clients):
            try:
                await ws.send_json(event)
            except Exception:
                self._clients.discard(ws)


# --------------------------------------------------------------------------- #
# session token file (so a local add-in can authenticate)
# --------------------------------------------------------------------------- #

def _token_file_path(db_path) -> str:
    override = os.environ.get("SANAD_TOKEN_FILE")
    if override:
        return override
    return str(Path(str(db_path)).resolve().parent / "sanad.token")


def _write_token_file(db_path, token: str) -> None:
    """Write the session token to a 0600 file next to the library so a legitimate
    local client (the editor add-in) can read it. Best-effort; never fatal."""
    try:
        p = Path(_token_file_path(db_path))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(token, encoding="utf-8")
        try:
            os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)  # rw for owner only
        except OSError:
            pass
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# app factory
# --------------------------------------------------------------------------- #

def create_app(db_path: str | Path = "sanad_library.db") -> FastAPI:
    app = FastAPI(title="SANAD the RefGuard — Core", version=__version__)
    app.state.db_path = str(db_path)
    app.state.events = EventHub()

    # --- security -------------------------------------------------------------
    # A researcher's work depends on this data being trustworthy, so the Core is
    # not left as an open localhost service. Three layers:
    #   1. A per-process bearer TOKEN (primary control). Every /v1 request must
    #      present it; a page or process that doesn't know it gets 401. The token
    #      is provided by the launcher via SANAD_TOKEN, or generated here, and is
    #      also written to a 0600 token file so a legitimate local client (the
    #      editor add-in) can read it. An attacker cannot know it, and browsers
    #      never auto-send an Authorization header, so cross-site forgery fails.
    #   2. A strict Host-header allow-list, to defeat DNS-rebinding.
    #   3. CORS scoped to loopback / file:// origins as defence in depth.
    token = os.environ.get("SANAD_TOKEN") or secrets.token_urlsafe(32)
    app.state.token = token
    _write_token_file(db_path, token)
    app.state.token_file = _token_file_path(db_path)

    async def _auth(request: Request, call_next):
        # preflight and the liveness probe are open; everything else needs the token
        if request.method == "OPTIONS" or request.url.path == "/v1/health":
            return await call_next(request)
        if not secrets.compare_digest(request.headers.get("authorization", ""),
                                      f"Bearer {token}"):
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
        return await call_next(request)

    from fastapi.middleware.cors import CORSMiddleware
    from starlette.middleware.trustedhost import TrustedHostMiddleware

    # add order matters: last-added runs outermost. We want
    # TrustedHost -> CORS -> auth -> routes.
    app.add_middleware(BaseHTTPMiddleware, dispatch=_auth)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^(https?://(localhost|127\.0\.0\.1)(:\d+)?|null|file://)$",
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost",
                       f"127.0.0.1:{DEFAULT_PORT}", f"localhost:{DEFAULT_PORT}",
                       "testserver"],  # testserver: FastAPI TestClient's Host
    )

    def get_conn():
        conn = db.connect(app.state.db_path)
        try:
            yield conn
        finally:
            conn.close()

    # -- health (unauthenticated liveness; reveals nothing sensitive) -------- #
    @app.get("/v1/health")
    def health():
        return {"status": "ok", "service": "sanad-core", "version": __version__,
                "auth": "required"}

    # -- library ------------------------------------------------------------ #
    @app.get("/v1/library/search")
    def library_search(q: str = "", limit: int = 20, conn=Depends(get_conn)):
        return {"results": documents.search_library(conn, q, limit)}

    @app.post("/v1/library/import")
    def library_import(req: ImportRequest, conn=Depends(get_conn)):
        if len(req.text) > MAX_IMPORT_CHARS or (req.data_b64 or "") and len(req.data_b64) > MAX_IMPORT_CHARS:
            raise HTTPException(413, f"import too large (>{MAX_IMPORT_CHARS} chars)")
        fmt = req.format.lower()
        # parse to (fields, authors) rows for every format, then optionally enrich
        # from Crossref, then insert -- one path so `resolve` works uniformly.
        if fmt == "ris":
            rows = [importer.ris_record_to_fields(r) for r in importer.parse_ris(req.text)]
        elif fmt == "bibtex":
            rows = [importer.bibtex_entry_to_fields(e) for e in importer.parse_bibtex(req.text)]
        elif fmt == "typed":
            rows = [importer.parse_typed_reference(r) for r in importer.split_typed_list(req.text)]
        elif fmt == "csv":
            rows = list_import.parse_csv(req.text)
        elif fmt in ("xlsx", "docx"):
            if not req.data_b64:
                raise HTTPException(400, f"{fmt} import requires base64 file data in 'data_b64'")
            try:
                data = base64.b64decode(req.data_b64, validate=True)
            except Exception:
                raise HTTPException(400, "data_b64 is not valid base64")
            rows = (list_import.parse_xlsx(data) if fmt == "xlsx"
                    else list_import.parse_docx(data))
        else:
            raise HTTPException(400, f"unknown import format {req.format!r} "
                                     "(expected ris | bibtex | typed | csv | xlsx | docx)")

        ids, resolved = [], 0
        for fields, authors in rows:
            if req.resolve:
                new_fields, authors = resolver.enrich(fields, authors)
                if new_fields.get("resolution_src") == "crossref":
                    resolved += 1
                fields = new_fields
            ids.append(importer.insert_reference(conn, fields, authors))
        conn.commit()
        count = conn.execute("SELECT COUNT(*) c FROM reference").fetchone()["c"]
        return {"imported": len(ids), "library_size": count, "resolved": resolved}

    # -- citations ---------------------------------------------------------- #
    @app.post("/v1/citations")
    def citation_create(body: CitationCreate, conn=Depends(get_conn)):
        if not body.reference_ids:
            raise HTTPException(400, "reference_ids must not be empty")
        cid, rendered = documents.create_citation(
            conn, body.document_id, body.reference_ids, body.raw_original_text
        )
        return {"citation_id": cid, "rendered_text": rendered}

    @app.put("/v1/citations/{citation_id}")
    def citation_update(citation_id: str, body: CitationUpdate, conn=Depends(get_conn)):
        rendered = documents.rerender_citation(conn, citation_id, body.reference_ids)
        if rendered is None:
            raise HTTPException(404, f"no citation {citation_id!r}")
        return {"citation_id": citation_id, "rendered_text": rendered}

    @app.get("/v1/documents/{document_id}/bibliography")
    def document_bibliography(document_id: str, conn=Depends(get_conn)):
        # entries + the Office-ready paragraph_style to apply to them (Sprint 6)
        return documents.bibliography_payload(conn, document_id)

    # -- integrity scan: Tier-A + Tier-B engine, LIVE ----------------------- #
    @app.post("/v1/documents/{document_id}/scan")
    async def document_scan(document_id: str, body: ScanRequest | None = None,
                            conn=Depends(get_conn)):
        body = body or ScanRequest()
        await app.state.events.broadcast(
            {"type": "scan-started", "document_id": document_id})

        # Tier-B runs only when the add-in sent citing sentences to check against.
        embedder = embedding.get_embedding_provider() if body.contexts else None
        flags = integrity.scan(
            conn, document_id,
            present_control_ids=body.present_control_ids,
            listed_reference_ids=body.listed_reference_ids,
            contexts=body.contexts, embedder=embedder,
        )
        open_count = sum(1 for f in flags if f["status"] == "open")
        await app.state.events.broadcast(
            {"type": "scan-complete", "document_id": document_id,
             "flag_count": len(flags), "open_count": open_count})
        # Report honestly whether the semantic check ran and on which backend --
        # a lexical-fallback result must never masquerade as a true semantic one.
        return {"flags": flags, "flag_count": len(flags), "open_count": open_count,
                "tier_b": {"ran": embedder is not None,
                           "backend": embedder.name if embedder else None}}

    @app.get("/v1/documents/{document_id}/flags")
    def document_flags(document_id: str, conn=Depends(get_conn)):
        return {"flags": integrity.list_flags(conn, document_id)}

    @app.put("/v1/flags/{flag_id}")
    def flag_update(flag_id: str, body: FlagStatusUpdate, conn=Depends(get_conn)):
        try:
            ok = integrity.set_flag_status(conn, flag_id, body.status)
        except ValueError as e:
            raise HTTPException(422, str(e))
        if not ok:
            raise HTTPException(404, f"no flag {flag_id!r}")
        return {"flag_id": flag_id, "status": body.status}

    # -- style profiles ----------------------------------------------------- #
    @app.post("/v1/style-profiles")
    def style_profile_create(profile: dict, conn=Depends(get_conn)):
        errors = sp.validate_profile(profile)
        if errors:
            raise HTTPException(422, {"errors": errors})
        pid = sp.save_profile(conn, profile)
        return {"id": pid}

    @app.post("/v1/style-profiles/build")
    def style_profile_build(form: dict, conn=Depends(get_conn)):
        # the guided-form backend: friendly answers -> a full .sanadstyle.json
        profile = sp.build_profile(form)
        errors = sp.validate_profile(profile)
        if errors:
            raise HTTPException(422, {"errors": errors})
        pid = sp.save_profile(conn, profile)
        profile["id"] = pid
        return {"id": pid, "profile": sp.to_sanadstyle_json(profile)}

    @app.get("/v1/style-profiles")
    def style_profiles_list(conn=Depends(get_conn)):
        return {"profiles": sp.list_profiles(conn)}

    @app.get("/v1/style-profiles/{profile_id}")
    def style_profile_get(profile_id: str, conn=Depends(get_conn)):
        prof = sp.get_profile(conn, profile_id)
        if prof is None:
            raise HTTPException(404, f"no style profile {profile_id!r}")
        return sp.to_sanadstyle_json(prof)

    @app.put("/v1/style-profiles/{profile_id}")
    def style_profile_update(profile_id: str, profile: dict, conn=Depends(get_conn)):
        if sp.get_profile(conn, profile_id) is None:
            raise HTTPException(404, f"no style profile {profile_id!r}")
        profile["id"] = profile_id  # the path is authoritative
        errors = sp.validate_profile(profile)
        if errors:
            raise HTTPException(422, {"errors": errors})
        sp.save_profile(conn, profile)  # save_profile upserts on id
        return {"id": profile_id}

    @app.delete("/v1/style-profiles/{profile_id}")
    def style_profile_delete(profile_id: str, conn=Depends(get_conn)):
        if not sp.delete_profile(conn, profile_id):
            raise HTTPException(404, f"no style profile {profile_id!r}")
        return {"deleted": profile_id}

    @app.post("/v1/style-profiles/{profile_id}/apply")
    def style_profile_apply(profile_id: str, body: StyleProfileApply, conn=Depends(get_conn)):
        if sp.get_profile(conn, profile_id) is None:
            raise HTTPException(404, f"no style profile {profile_id!r}")
        n = documents.set_document_profile(conn, body.document_id, profile_id)
        return {"rerendered_citations": n,
                "bibliography": documents.render_bibliography(conn, body.document_id)}

    # -- handbook parse: v1.x (honest 501, never a fabricated profile) ------ #
    @app.post("/v1/handbook/parse")
    def handbook_parse():
        raise HTTPException(
            501,
            "Handbook parsing is a v1.x feature (MVP_SPEC.md §4/§8). Until then, "
            "build a Style Profile via POST /v1/style-profiles.",
        )

    # -- events (server -> add-in push channel) ----------------------------- #
    @app.websocket("/v1/events")
    async def events(ws: WebSocket):
        # a browser WebSocket cannot set an Authorization header, so the token
        # is passed as a query parameter (?token=...) and checked before accept.
        if not secrets.compare_digest(ws.query_params.get("token", ""), token):
            await ws.close(code=1008)  # policy violation
            return
        await ws.accept()
        app.state.events.register(ws)
        await ws.send_json({"type": "connected", "service": "sanad-core",
                            "version": __version__})
        try:
            while True:
                # client->server pings confirm liveness; server->client scan
                # events arrive via EventHub.broadcast (see /scan).
                msg = await ws.receive_text()
                await ws.send_json({"type": "pong", "echo": msg})
        except WebSocketDisconnect:
            return
        finally:
            app.state.events.unregister(ws)

    return app


def serve(db_path: str | Path = "sanad_library.db",
          host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:  # pragma: no cover
    import uvicorn
    uvicorn.run(create_app(db_path), host=host, port=port)


if __name__ == "__main__":  # pragma: no cover
    serve()
