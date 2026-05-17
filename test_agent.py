import json
import os
import re
import tempfile

import pytest

import tools
from agent import MemoryStore, SESSION_DATES, execute_tool


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


def test_save_upserts_existing_session_id():
    path = _tmp_path()
    m = MemoryStore(path)
    m.save({"session_id": 1, "date": "2025-11-03", "summary": "first run", "commitments": [], "insights": []})
    m.save({"session_id": 1, "date": "2025-11-03", "summary": "second run", "commitments": [], "insights": []})
    assert len(m.data["sessions"]) == 1
    assert m.data["sessions"][0]["summary"] == "second run"
    os.unlink(path)


def test_format_for_prompt_excludes_current_session():
    path = _tmp_path()
    m = MemoryStore(path)
    m.save({"session_id": 1, "date": "2025-11-03", "summary": "session 1 summary", "commitments": [], "insights": []})
    assert "session 1 summary" not in m.format_for_prompt(exclude_session_id=1)
    assert "session 1 summary" in m.format_for_prompt(exclude_session_id=2)
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


# ── execute_tool ──────────────────────────────────────────────────────────────

def test_transactions_includes_category_totals():
    tools.CURRENT_SESSION = 1
    result = execute_tool("get_recent_transactions", {"days": 35})
    assert "category_totals_inr" in result
    assert "total_debits_inr" in result
    assert "total_credits_inr" in result
    assert result["category_totals_inr"]["food_delivery"] > 0


def test_transactions_credits_match_salary():
    tools.CURRENT_SESSION = 1
    result = execute_tool("get_recent_transactions", {"days": 35})
    assert result["total_credits_inr"] == 120000


def test_bills_includes_total_due():
    tools.CURRENT_SESSION = 1
    result = execute_tool("get_upcoming_bills", {"days": 30})
    assert "total_due_inr" in result
    assert "bills" in result
    expected = sum(b["amount"] for b in result["bills"])
    assert result["total_due_inr"] == expected


def test_set_reminder_returns_confirmation():
    result = execute_tool("set_reminder", {
        "date": "2025-11-25",
        "content": "Transfer ₹30,000 to house fund",
    })
    assert result["status"] == "set"
    assert result["date"] == "2025-11-25"


def test_unknown_tool_returns_error_dict():
    result = execute_tool("nonexistent_tool", {})
    assert "error" in result


# ── build_system_prompt ───────────────────────────────────────────────────────

from agent import build_system_prompt


def test_session1_prompt_has_correct_date():
    path = _tmp_path()
    m = MemoryStore(path)
    prompt = build_system_prompt(m, 1)
    assert "2025-11-03" in prompt
    assert "November 2025" in prompt


def test_session2_prompt_has_correct_date():
    path = _tmp_path()
    m = MemoryStore(path)
    prompt = build_system_prompt(m, 2)
    assert "2025-11-06" in prompt
    assert "November 2025" in prompt


def test_prompt_includes_user_profile():
    path = _tmp_path()
    m = MemoryStore(path)
    prompt = build_system_prompt(m, 1)
    assert "Priya Sharma" in prompt
    assert "120,000" in prompt


def test_prompt_shows_no_previous_sessions_when_memory_empty():
    path = _tmp_path()
    m = MemoryStore(path)
    prompt = build_system_prompt(m, 1)
    assert "No previous sessions." in prompt


def test_prompt_injects_memory_from_session1():
    path = _tmp_path()
    m = MemoryStore(path)
    m.save({
        "session_id": 1,
        "date": "2025-11-03",
        "summary": "User committed to ₹30k savings",
        "commitments": ["Transfer ₹30,000 on 2025-11-25"],
        "insights": [],
    })
    prompt = build_system_prompt(m, 2)
    assert "Transfer ₹30,000 on 2025-11-25" in prompt
    os.unlink(path)
