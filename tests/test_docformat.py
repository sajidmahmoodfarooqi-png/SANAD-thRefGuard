"""Thesis .docx reformatting: applies the profile, never changes prose, stays offline."""
import base64
import io

import pytest
from fastapi.testclient import TestClient

from sanad_core import docformat
from sanad_core.server import create_app

PROSE = [
    "Chapter 1: Introduction",
    "This is the researcher's own sentence and it must never change.",
    "A second paragraph with specific wording: azimuth, provenance, 1948.",
]


def _thesis_docx():
    from docx import Document
    doc = Document()
    for line in PROSE:
        doc.add_paragraph(line)
    buf = io.BytesIO(); doc.save(buf); return buf.getvalue()


PROFILE = {
    "paragraph_style": {"font_family": "Georgia", "font_size_pt": 13, "line_spacing": 2.0,
                        "bibliography_hanging_indent_cm": 1.27},
    "document_structure": {"enabled": True, "margin_cm": 2.54},
}


def test_reformat_applies_and_never_touches_prose():
    data = _thesis_docx()
    before = docformat.text_fingerprint(data)
    result = docformat.apply_profile_to_docx(data, PROFILE)
    after = docformat.text_fingerprint(result["data"])
    assert before == after == PROSE          # every word identical, before and after
    # formatting really landed on the Normal style
    from docx import Document
    from docx.shared import Pt
    doc = Document(io.BytesIO(result["data"]))
    normal = doc.styles["Normal"]
    assert normal.font.name == "Georgia"
    assert normal.font.size == Pt(13)
    assert abs(doc.sections[0].top_margin.cm - 2.54) < 0.01
    assert any("Body font" in a for a in result["applied"])


def test_reformat_rejects_non_docx():
    with pytest.raises(ValueError):
        docformat.apply_profile_to_docx(b"not a docx at all", PROFILE)


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "fmt.db")
    c = TestClient(app); c.headers.update({"Authorization": f"Bearer {app.state.token}"})
    return c


def test_api_format_with_inline_profile(client):
    data = _thesis_docx()
    r = client.post("/v1/documents/format", json={
        "data_b64": base64.b64encode(data).decode(), "profile": PROFILE})
    assert r.status_code == 200
    body = r.json()
    assert body["applied"]
    # returned file is a real docx with identical prose
    out = base64.b64decode(body["data_b64"])
    assert docformat.text_fingerprint(out) == PROSE


def test_api_format_with_saved_profile_id(client):
    pid = client.post("/v1/style-profiles/build", json={
        "name": "Test Uni", "based_on_csl": "apa", "font_family": "Cambria",
        "font_size_pt": 12, "margin_cm": 3.0}).json()["id"]
    data = _thesis_docx()
    r = client.post("/v1/documents/format", json={
        "data_b64": base64.b64encode(data).decode(), "profile_id": pid})
    assert r.status_code == 200 and r.json()["applied"]


def test_api_format_bad_base64_is_400(client):
    r = client.post("/v1/documents/format", json={"data_b64": "!!!not base64!!!", "profile": PROFILE})
    assert r.status_code == 400


def test_api_format_missing_profile_is_400(client):
    data = base64.b64encode(_thesis_docx()).decode()
    r = client.post("/v1/documents/format", json={"data_b64": data})
    assert r.status_code == 400
