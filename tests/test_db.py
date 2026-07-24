import pytest

from sanad_core import db


def test_schema_creates_all_expected_tables():
    conn = db.connect()
    expected = {
        "author", "citation", "document", "integrity_flag",
        "local_pdf", "reference", "reference_author", "style_profile",
    }
    assert expected == set(db.table_names(conn))


def test_new_id_is_unique():
    ids = {db.new_id() for _ in range(1000)}
    assert len(ids) == 1000


def test_now_iso_is_parseable_and_utc():
    from datetime import datetime
    ts = db.now_iso()
    parsed = datetime.fromisoformat(ts)
    assert parsed.utcoffset().total_seconds() == 0


def test_insert_and_select_roundtrip():
    conn = db.connect()
    rid = db.new_id()
    conn.execute(
        "INSERT INTO reference (id, item_type, title, csl_json, created_at) VALUES (?,?,?,?,?)",
        (rid, "book", "Test Title", "{}", db.now_iso()),
    )
    conn.commit()
    row = conn.execute("SELECT title, item_type FROM reference WHERE id = ?", (rid,)).fetchone()
    assert row["title"] == "Test Title"
    assert row["item_type"] == "book"


def test_foreign_keys_enforced():
    conn = db.connect()
    with pytest.raises(Exception):
        conn.execute(
            "INSERT INTO reference_author (reference_id, author_id, position) VALUES (?,?,?)",
            ("nonexistent-ref", "nonexistent-author", 0),
        )
        conn.commit()
