import json
import os
import re
import tempfile

import pytest

import tools
from agent import MemoryStore, SESSION_DATES


# ── helpers ───────────────────────────────────────────────────────────────────

def _tmp_path():
    """Return a temp file path that does not yet exist."""
    f = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    path = f.name
    f.close()
    os.unlink(path)
    return path


# ── MemoryStore ───────────────────────────────────────────────────────────────

def test_empty_memory_has_no_sessions():
    path = _tmp_path()
    m = MemoryStore(path)
    assert m.data == {"sessions": []}


def test_empty_memory_formats_as_no_previous_sessions():
    path = _tmp_path()
    m = MemoryStore(path)
    assert m.format_for_prompt() == "No previous sessions."


def test_save_persists_to_disk():
    path = _tmp_path()
    m = MemoryStore(path)
    record = {
        "session_id": 1,
        "date": "2025-11-03",
        "summary": "User committed to ₹30k savings",
        "commitments": ["Transfer ₹30,000 on 2025-11-25"],
        "insights": ["Food delivery overspend"],
    }
    m.save(record)
    m2 = MemoryStore(path)
    assert len(m2.data["sessions"]) == 1
    assert m2.data["sessions"][0]["session_id"] == 1
    os.unlink(path)


def test_format_for_prompt_includes_commitment_and_insight():
    path = _tmp_path()
    m = MemoryStore(path)
    m.save({
        "session_id": 1,
        "date": "2025-11-03",
        "summary": "User committed to ₹30k savings",
        "commitments": ["Transfer ₹30,000 on 2025-11-25"],
        "insights": ["Food delivery: ₹10,640"],
    })
    prompt = m.format_for_prompt()
    assert "Session 1 (2025-11-03)" in prompt
    assert "Transfer ₹30,000 on 2025-11-25" in prompt
    assert "Food delivery: ₹10,640" in prompt
    os.unlink(path)
