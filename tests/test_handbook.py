"""Handbook detect-and-confirm parser tests (local, no network)."""
import base64
import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from sanad_core import handbook
from sanad_core.server import create_app

MANUAL = """
University of Somewhere — Thesis Format Manual

All theses must be typed in Times New Roman, 12 point, and double-spaced.
Leave a margin of 1 inch on all sides.
References must follow APA style (7th edition) and use a hanging indent of 0.5 inch.
"""


def _docx_bytes(paragraphs):
    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    ps = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    doc = f'<?xml version="1.0"?><w:document xmlns:w="{W}"><w:body>{ps}</w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", doc)
    return buf.getvalue()


def test_detect_rules_finds_the_common_directives():
    out = handbook.detect_rules(MANUAL)
    f = out["form"]
    assert f["based_on_csl"] == "apa"
    assert f["font_family"] == "Times New Roman"
    assert f["font_size_pt"] == 12
    assert f["line_spacing"] == 2.0
    assert f["margin_cm"] == pytest.approx(2.54, abs=0.01)
    assert f["hanging_indent_cm"] == pytest.approx(1.27, abs=0.01)
    # every detected value carries the snippet it came from
    assert all("evidence" in d and d["evidence"] for d in out["detected"])


def test_detect_rules_reports_what_it_cannot_find():
    out = handbook.detect_rules("This manual says nothing about formatting at all.")
    assert out["form"] == {} or "based_on_csl" not in out["form"]
    assert out["notes"]  # tells the user what to set themselves


def test_extract_text_from_docx():
    data = _docx_bytes(["Use MLA style.", "Font: Arial 11 point."])
    text = handbook.extract_text(data, "docx")
    assert "MLA" in text and "Arial" in text


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "hb.db")
    c = TestClient(app)
    c.headers.update({"Authorization": f"Bearer {app.state.token}"})
    return c


def test_api_parse_txt(client):
    r = client.post("/v1/handbook/parse", json={"format": "txt", "text": MANUAL})
    assert r.status_code == 200
    assert r.json()["form"]["based_on_csl"] == "apa"


def test_api_parse_docx_base64(client):
    data = _docx_bytes(["Thesis must use IEEE style, Calibri 12 point, single-spaced."])
    r = client.post("/v1/handbook/parse",
                    json={"format": "docx", "data_b64": base64.b64encode(data).decode()})
    assert r.status_code == 200
    f = r.json()["form"]
    assert f["based_on_csl"] == "ieee" and f["font_family"] == "Calibri"


def test_api_parse_unknown_format_is_400(client):
    r = client.post("/v1/handbook/parse", json={"format": "rtf", "text": "x"})
    assert r.status_code == 400


def test_extract_text_from_pdf():
    fitz = pytest.importorskip("fitz")  # PyMuPDF
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Thesis must use Vancouver style, Arial 11 point.")
    data = doc.tobytes()
    text = handbook.extract_text(data, "pdf")
    assert "Vancouver" in text and "Arial" in text
