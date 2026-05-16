# Finance Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python finance companion agent in a single `agent.py` file that runs two sessions for Priya Sharma, demonstrating memory persistence, tool calling, tool-vs-memory discipline, and judgment — using only the Anthropic SDK with no frameworks.

**Architecture:** Five components in one file: `TOOL_DEFINITIONS` (tool schemas Claude reads), `execute_tool()` (dispatcher that pre-computes arithmetic in Python before Claude sees results), `MemoryStore` (reads/writes `memory.json`), `build_system_prompt()` (assembles Claude's instructions + memory + today's date), and `Agent` (the while-True agentic loop + session runner + memory extraction).

**Tech Stack:** Python 3.11+, `anthropic` SDK, stdlib only (`json`, `os`, `re`, `sys`, `datetime`), `pytest` for tests.

---

## Files

| File | Status | Responsibility |
|---|---|---|
| `tools.py` | Provided — do not modify | Mock tool implementations |
| `sessions.md` | Provided — do not modify | Exact user messages for both sessions |
| `agent.py` | Create | Full agent (~250 lines) |
| `test_agent.py` | Create | Unit tests for MemoryStore, execute_tool, build_system_prompt |
| `memory.json` | Auto-created at runtime | Persisted memory after Session 1 |

All files live in the same directory: `/Users/dhruvtri/Downloads/drive-download-20260515T042333Z-3-001/`

---

## Task 1: Environment Setup

**Files:** none (terminal only)

- [ ] **Step 1: Check Python version**

```bash
python3 --version
```

Expected: `Python 3.11.x` or higher. If not installed, download from [python.org](https://python.org).

- [ ] **Step 2: Create a virtual environment**

A virtual environment is an isolated Python installation for this project — like a project-scoped dependency container in Java (similar concept to Maven's local repo, but per-project).

```bash
cd /Users/dhruvtri/Downloads/drive-download-20260515T042333Z-3-001
python3 -m venv .venv
```

Expected: a `.venv/` folder appears.

- [ ] **Step 3: Activate the virtual environment**

```bash
source .venv/bin/activate
```

Expected: your terminal prompt now starts with `(.venv)`. Every `pip install` and `python` command now runs inside this environment.

- [ ] **Step 4: Install dependencies**

```bash
pip install anthropic pytest
```

Expected: output showing packages installing, ending with `Successfully installed anthropic-X.X.X ...`

- [ ] **Step 5: Set your Anthropic API key**

Get your key from [console.anthropic.com](https://console.anthropic.com) → API Keys → Create Key.

```bash
export ANTHROPIC_API_KEY="sk-ant-api03-..."
```

Verify it's set:
```bash
echo $ANTHROPIC_API_KEY
```

Expected: your key prints. Note: this only lasts for the current terminal session. If you open a new terminal, run `export` again (or add it to `~/.zshrc`).

- [ ] **Step 6: Verify the anthropic SDK works**

```bash
python3 -c "import anthropic; print('anthropic SDK imported successfully')"
```

Expected: `anthropic SDK imported successfully`

---

## Task 2: Create `agent.py` Skeleton

**Files:**
- Create: `agent.py`

This gives us a file that imports correctly and defines all components as stubs. We'll fill each in during subsequent tasks. This is like defining all your Java class interfaces before implementing them.

- [ ] **Step 1: Create the skeleton**

Create `/Users/dhruvtri/Downloads/drive-download-20260515T042333Z-3-001/agent.py` with this exact content:

```python
import json
import os
import re
import sys
from datetime import datetime

import anthropic
from tools import (
    get_recent_transactions,
    get_account_balance,
    get_upcoming_bills,
    set_reminder,
)

USER_PROFILE = {
    "name": "Priya Sharma",
    "age": 28,
    "city": "Bangalore",
    "monthly_income_inr": 120000,
    "stated_goal": "Save ₹15 lakh in 2 years for a house down payment in Bangalore",
}

SESSION_DATES = {1: "2025-11-03", 2: "2025-11-06"}

TOOL_DEFINITIONS = []  # Task 3


def execute_tool(name: str, args: dict):
    pass  # Task 4


class MemoryStore:
    pass  # Task 5


def build_system_prompt(memory, session_num: int) -> str:
    pass  # Task 6


class Agent:
    def __init__(self, memory):
        self.memory = memory
        self.client = anthropic.Anthropic()

    def _agent_loop(self, system: str, messages: list) -> str:
        pass  # Task 7

    def run_session(self, session_num: int, user_turns: list):
        pass  # Task 8

    def _extract_and_save_memory(self, session_num: int, messages: list):
        pass  # Task 8


SESSIONS = {}  # Task 9

if __name__ == "__main__":
    pass  # Task 9
```

- [ ] **Step 2: Verify the skeleton imports without errors**

```bash
python3 -c "import agent; print('agent.py imports OK')"
```

Expected: `agent.py imports OK`

- [ ] **Step 3: Commit**

```bash
git add agent.py
git commit -m "feat: add agent.py skeleton with stubs for all components"
```

---

## Task 3: TOOL_DEFINITIONS

**Files:**
- Modify: `agent.py` — replace `TOOL_DEFINITIONS = []` with the full schemas

These JSON schemas are how Claude learns what tools exist. Claude reads the `name` and `description` fields to decide when to call each tool. The `input_schema` tells it what arguments to provide.

- [ ] **Step 1: Replace TOOL_DEFINITIONS**

Replace the `TOOL_DEFINITIONS = []` line in `agent.py` with:

```python
TOOL_DEFINITIONS = [
    {
        "name": "get_recent_transactions",
        "description": (
            "Get user's transactions from the last N days. "
            "Use this to analyze spending patterns or check recent activity."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "How many days back to fetch",
                }
            },
            "required": ["days"],
        },
    },
    {
        "name": "get_account_balance",
        "description": (
            "Get current account balances. Always call this for up-to-date numbers "
            "— never use remembered balances, they go stale between sessions."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_upcoming_bills",
        "description": "Get bills due in the next N days.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "How many days ahead to look",
                }
            },
            "required": ["days"],
        },
    },
    {
        "name": "set_reminder",
        "description": "Set a reminder for the user on a specific date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format",
                },
                "content": {
                    "type": "string",
                    "description": "What to remind the user",
                },
            },
            "required": ["date", "content"],
        },
    },
]
```

- [ ] **Step 2: Verify still imports cleanly**

```bash
python3 -c "from agent import TOOL_DEFINITIONS; print(f'{len(TOOL_DEFINITIONS)} tools defined')"
```

Expected: `4 tools defined`

- [ ] **Step 3: Commit**

```bash
git add agent.py
git commit -m "feat: add TOOL_DEFINITIONS with 4 tool schemas"
```

---

## Task 4: MemoryStore (TDD)

**Files:**
- Create: `test_agent.py`
- Modify: `agent.py` — implement `MemoryStore` class

MemoryStore is the DAO (data access object) for `memory.json`. It loads at startup, saves after Session 1, and formats its contents for injection into the system prompt.

- [ ] **Step 1: Create `test_agent.py` with MemoryStore tests**

```python
import json
import os
import re
import tempfile

import pytest

import tools
from agent import MemoryStore, SESSION_DATES


# ── MemoryStore ──────────────────────────────────────────────────────────────

def _tmp_path():
    """Return a temp file path that does not yet exist."""
    f = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    path = f.name
    f.close()
    os.unlink(path)
    return path


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
    # Load fresh instance from disk
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
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
python3 -m pytest test_agent.py -v
```

Expected: 4 failures like `AttributeError: type object 'MemoryStore' has no attribute ...` — because MemoryStore is still a stub.

- [ ] **Step 3: Implement MemoryStore in `agent.py`**

Replace `class MemoryStore: pass` with:

```python
class MemoryStore:
    def __init__(self, path: str = "memory.json"):
        self.path = path
        self.data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.path):
            with open(self.path) as f:
                return json.load(f)
        return {"sessions": []}

    def save(self, session_record: dict):
        self.data["sessions"].append(session_record)
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)
        print(f"  [MEMORY SAVED] {self.path}")

    def format_for_prompt(self) -> str:
        if not self.data["sessions"]:
            return "No previous sessions."
        lines = []
        for s in self.data["sessions"]:
            lines.append(f"Session {s['session_id']} ({s['date']}):")
            lines.append(f"  Summary: {s['summary']}")
            for c in s.get("commitments", []):
                lines.append(f"  Commitment: {c}")
            for i in s.get("insights", []):
                lines.append(f"  Insight: {i}")
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
python3 -m pytest test_agent.py -v
```

Expected:
```
test_agent.py::test_empty_memory_has_no_sessions PASSED
test_agent.py::test_empty_memory_formats_as_no_previous_sessions PASSED
test_agent.py::test_save_persists_to_disk PASSED
test_agent.py::test_format_for_prompt_includes_commitment_and_insight PASSED
```

- [ ] **Step 5: Commit**

```bash
git add agent.py test_agent.py
git commit -m "feat: implement MemoryStore with TDD (load/save/format)"
```

---

## Task 5: `execute_tool()` (TDD)

**Files:**
- Modify: `test_agent.py` — add execute_tool tests
- Modify: `agent.py` — implement `execute_tool`

This function receives Claude's tool call (a name + args dict), runs the actual function from `tools.py`, and returns a result enriched with Python-computed totals. Arithmetic happens here, not in the LLM.

- [ ] **Step 1: Add execute_tool tests to `test_agent.py`**

Append these tests to the end of `test_agent.py`:

```python
# ── execute_tool ─────────────────────────────────────────────────────────────

from agent import execute_tool


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
    # Nov 1 salary credit is ₹1,20,000 — should appear in total_credits_inr
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
```

- [ ] **Step 2: Run tests — expect the new ones to FAIL**

```bash
python3 -m pytest test_agent.py -v -k "execute_tool or transactions or bills or reminder or unknown"
```

Expected: 5 failures — `execute_tool` returns `None` (it's still a stub).

- [ ] **Step 3: Implement `execute_tool` in `agent.py`**

Replace `def execute_tool(name: str, args: dict): pass` with:

```python
def execute_tool(name: str, args: dict) -> dict:
    print(f"  [TOOL CALL] {name}({args})")

    if name == "get_recent_transactions":
        txns = get_recent_transactions(args["days"])
        by_category: dict = {}
        for t in txns:
            cat = t["category"]
            by_category[cat] = by_category.get(cat, 0) + abs(t["amount"])
        result = {
            "transactions": txns,
            "category_totals_inr": by_category,
            "total_debits_inr": sum(abs(t["amount"]) for t in txns if t["amount"] < 0),
            "total_credits_inr": sum(t["amount"] for t in txns if t["amount"] > 0),
        }
    elif name == "get_account_balance":
        result = get_account_balance()
    elif name == "get_upcoming_bills":
        bills = get_upcoming_bills(args.get("days", 30))
        result = {
            "bills": bills,
            "total_due_inr": sum(b["amount"] for b in bills),
        }
    elif name == "set_reminder":
        result = set_reminder(args["date"], args["content"])
    else:
        result = {"error": f"Unknown tool: {name}"}

    print(f"  [TOOL RESULT] {json.dumps(result)}\n")
    return result
```

- [ ] **Step 4: Run all tests — expect all PASS**

```bash
python3 -m pytest test_agent.py -v
```

Expected: all 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add agent.py test_agent.py
git commit -m "feat: implement execute_tool with Python pre-computation (TDD)"
```

---

## Task 6: `build_system_prompt()` (TDD)

**Files:**
- Modify: `test_agent.py` — add build_system_prompt tests
- Modify: `agent.py` — implement `build_system_prompt`

This function assembles Claude's instructions as a string. It injects today's date (from code, not inferred by LLM), the user profile, memory from previous sessions, and behavior rules.

- [ ] **Step 1: Add build_system_prompt tests to `test_agent.py`**

Append to `test_agent.py`:

```python
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
    assert "120,000" in prompt  # monthly income formatted with comma


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
```

- [ ] **Step 2: Run new tests — expect FAIL**

```bash
python3 -m pytest test_agent.py -v -k "prompt"
```

Expected: 5 failures — `build_system_prompt` returns `None`.

- [ ] **Step 3: Implement `build_system_prompt` in `agent.py`**

Replace `def build_system_prompt(memory, session_num: int) -> str: pass` with:

```python
def build_system_prompt(memory: MemoryStore, session_num: int) -> str:
    today = SESSION_DATES[session_num]
    month_year = datetime.strptime(today, "%Y-%m-%d").strftime("%B %Y")
    return f"""You are a personal finance companion for {USER_PROFILE['name']}.

TODAY'S DATE: {today} ({month_year})
If the user specifies a full date (e.g. "25th May 2026", "December 15"), use exactly what they said. If they refer to a date by day only (e.g. "the 25th", "on Friday") with no month or year, interpret it relative to today's date above — do not guess based on the current real-world date.

USER PROFILE:
- Age: {USER_PROFILE['age']}, {USER_PROFILE['city']}
- Monthly income: ₹{USER_PROFILE['monthly_income_inr']:,} (credited on the 1st of each month)
- Primary goal: {USER_PROFILE['stated_goal']}

MEMORY FROM PREVIOUS SESSIONS:
{memory.format_for_prompt()}

BEHAVIOR RULES:
1. For any current financial numbers (balances, upcoming bills), always call the relevant tool — never quote numbers from memory, they go stale.
2. For user commitments, goals, and plans — use memory. These are durable.
3. When the user asks something new, check if it connects to existing commitments before answering.
4. Tool results include pre-computed totals (category_totals_inr, total_due_inr). Use those numbers directly — do not recalculate.
5. Be warm but direct. One or two paragraphs max per response.
"""
```

- [ ] **Step 4: Run all tests — expect all PASS**

```bash
python3 -m pytest test_agent.py -v
```

Expected: all 14 tests pass.

- [ ] **Step 5: Commit**

```bash
git add agent.py test_agent.py
git commit -m "feat: implement build_system_prompt with date injection (TDD)"
```

---

## Task 7: `Agent._agent_loop()`

**Files:**
- Modify: `agent.py` — implement `_agent_loop`

This is the heart of the agent. It calls Claude, checks if Claude wants to use a tool, executes it, feeds the result back, and loops until Claude produces a final text response.

No unit test here — `_agent_loop` requires a live Anthropic API call. We'll verify it works with a smoke test.

- [ ] **Step 1: Implement `_agent_loop` in `agent.py`**

Replace `def _agent_loop(self, system: str, messages: list) -> str: pass` with:

```python
    def _agent_loop(self, system: str, messages: list) -> str:
        while True:
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=system,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        })
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

            else:
                for block in response.content:
                    if hasattr(block, "text"):
                        return block.text
```

- [ ] **Step 2: Smoke test with a single API call**

Run this one-liner to verify the loop works (costs ~1 API call):

```bash
python3 -c "
import agent, tools
tools.CURRENT_SESSION = 1
m = agent.MemoryStore('/tmp/test_memory.json')
a = agent.Agent(m)
system = agent.build_system_prompt(m, 1)
messages = [{'role': 'user', 'content': 'What is 2+2? Answer in one word.'}]
reply = a._agent_loop(system, messages)
print('Reply:', reply)
assert len(reply) > 0, 'Expected a non-empty reply'
print('Smoke test PASSED')
"
```

Expected: Claude replies with something like `"Four."` and you see `Smoke test PASSED`.

- [ ] **Step 3: Commit**

```bash
git add agent.py
git commit -m "feat: implement Agent._agent_loop (core agentic while-True loop)"
```

---

## Task 8: `run_session`, `_extract_and_save_memory`, `SESSIONS`, `main()`

**Files:**
- Modify: `agent.py` — implement all remaining stubs

These three pieces wire everything together: `run_session` iterates user turns through the loop, `_extract_and_save_memory` uses Claude Haiku to pull durable facts from the conversation and write them to disk, and `main` is the entry point.

- [ ] **Step 1: Implement `run_session` in `agent.py`**

Replace `def run_session(self, session_num: int, user_turns: list): pass` with:

```python
    def run_session(self, session_num: int, user_turns: list):
        system = build_system_prompt(self.memory, session_num)
        messages = []

        for user_msg in user_turns:
            print(f"\n{'─' * 60}")
            print(f"User: {user_msg}")
            messages.append({"role": "user", "content": user_msg})

            reply = self._agent_loop(system, messages)
            messages.append({"role": "assistant", "content": reply})
            print(f"\nAgent: {reply}")

        if session_num == 1:
            self._extract_and_save_memory(session_num, messages)
```

- [ ] **Step 2: Implement `_extract_and_save_memory` in `agent.py`**

Replace `def _extract_and_save_memory(self, session_num: int, messages: list): pass` with:

```python
    def _extract_and_save_memory(self, session_num: int, messages: list):
        extraction_prompt = """From this conversation, extract exactly:
1. A one-sentence summary of what happened
2. Any explicit commitments the user made (amounts, dates, actions) as a list
3. Key financial insights worth remembering (spending patterns, stated goals) as a list

Return ONLY valid JSON in this shape:
{"summary": "...", "commitments": ["..."], "insights": ["..."]}

Do NOT include balances or transaction amounts — those will be fetched fresh next session."""

        response = self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=extraction_prompt,
            messages=messages,
        )

        raw = response.content[0].text
        try:
            record = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            record = json.loads(match.group()) if match else {
                "summary": "Session completed.",
                "commitments": [],
                "insights": [],
            }

        record["session_id"] = session_num
        record["date"] = SESSION_DATES[session_num]
        self.memory.save(record)
        print(f"\n[MEMORY] Saved: {json.dumps(record, indent=2)}")
```

- [ ] **Step 3: Implement `SESSIONS` and `main()` in `agent.py`**

Replace `SESSIONS = {}` and `if __name__ == "__main__": pass` with:

```python
SESSIONS = {
    1: [
        "I just got my salary credited. Help me figure out how much I can realistically save this month.",
        "I feel like I'm spending too much on food delivery. How much did I actually spend on it last month?",
        "Okay that's worse than I thought. Let's say I want to cut that in half AND put aside ₹30,000 for my house fund this month — is that realistic given my upcoming bills?",
        "Got it. Remind me to actually transfer the ₹30,000 to my house fund on the 25th.",
    ],
    2: [
        "Hey, my colleague is selling his MacBook for ₹80,000, barely used. I've been wanting to upgrade. Should I buy it?",
    ],
}

if __name__ == "__main__":
    session_num = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    memory = MemoryStore()
    agent = Agent(memory)
    agent.run_session(session_num, SESSIONS[session_num])
```

- [ ] **Step 4: Verify all unit tests still pass**

```bash
python3 -m pytest test_agent.py -v
```

Expected: all 14 tests pass.

- [ ] **Step 5: Commit**

```bash
git add agent.py
git commit -m "feat: wire up run_session, memory extraction, SESSIONS, and main()"
```

---

## Task 9: Session 1 End-to-End

**Files:**
- Check: `tools.py` — confirm `CURRENT_SESSION = 1`
- Runtime: `memory.json` — will be created after this task

- [ ] **Step 1: Confirm `CURRENT_SESSION = 1` in `tools.py`**

Open `tools.py` and verify line 12 reads:
```python
CURRENT_SESSION = 1
```

Do not change anything else in this file.

- [ ] **Step 2: Run Session 1 and capture the transcript**

```bash
python3 agent.py 1 | tee session1_transcript.txt
```

This runs the agent and saves everything printed to `session1_transcript.txt`. It will take 1-2 minutes (4 user turns, each may involve multiple API calls).

- [ ] **Step 3: Verify the transcript looks right**

Open `session1_transcript.txt` and confirm all of these appear:

- `[TOOL CALL] get_recent_transactions` — appears when Priya asks about food delivery
- `[TOOL CALL] get_upcoming_bills` — appears when checking if ₹30,000 is realistic
- `[TOOL CALL] set_reminder` with `date: "2025-11-25"` — appears at turn 4
- `Agent:` responses after each user turn (4 total)
- `[MEMORY SAVED] memory.json` — at the very end
- `[MEMORY] Saved: { ... }` — showing the extracted JSON

- [ ] **Step 4: Verify `memory.json` was created and looks sensible**

```bash
cat memory.json
```

Expected: a JSON file with a `sessions` array containing one object. Check that:
- `"commitments"` contains something about ₹30,000 and the 25th
- `"insights"` mentions food delivery spending
- There are **no** balance numbers (e.g., no `128000` or `99820`) — those are dynamic, not stored

- [ ] **Step 5: Commit transcript**

```bash
git add session1_transcript.txt memory.json
git commit -m "docs: add Session 1 transcript and memory.json"
```

---

## Task 10: Session 2 End-to-End

**Files:**
- Modify: `tools.py` — flip `CURRENT_SESSION` to `2` (as instructed by the assignment)

Session 2 is the real test. The agent must connect a new question (MacBook purchase) to the savings plan from Monday — using memory for context and tools for fresh numbers.

- [ ] **Step 1: Flip `CURRENT_SESSION` to `2` in `tools.py`**

Change line 12 of `tools.py` from:
```python
CURRENT_SESSION = 1
```
to:
```python
CURRENT_SESSION = 2
```

This simulates Thursday Nov 6: rent has been paid, a few more food orders have come in, and the balance is lower.

- [ ] **Step 2: Run Session 2 and capture the transcript**

```bash
python3 agent.py 2 | tee session2_transcript.txt
```

- [ ] **Step 3: Verify all four assignment requirements in the transcript**

Open `session2_transcript.txt` and check each requirement:

**Requirement 1 — Memory:** The agent's response must reference the savings plan from Monday. Look for mention of ₹30,000, the house fund, or the Nov 25 commitment in the `Agent:` response.

**Requirement 2 — Judgment:** The agent must connect the MacBook question to the savings plan ON ITS OWN — without being told to. The response should explain why the MacBook purchase is a concern given the existing commitment.

**Requirement 3 — Tool discipline:** Look for these tool calls in the logs:
- `[TOOL CALL] get_account_balance` — must appear (fresh balance: ₹99,820)
- `[TOOL CALL] get_upcoming_bills` — must appear (remaining bills: ₹21,500)
- The response must NOT cite ₹1,28,000 (that was Monday's balance — stale)

**Requirement 4 — Tool action:** Look for:
- `[TOOL CALL] set_reminder` — must appear with a relevant content

- [ ] **Step 4: Commit transcript**

```bash
git add session2_transcript.txt
git commit -m "docs: add Session 2 transcript — all 4 requirements verified"
```

- [ ] **Step 5: Check line count**

```bash
wc -l agent.py
```

Expected: under 300. If over, look for unnecessary blank lines or comments to trim.

---

## Self-Review Against Spec

**Spec coverage check:**

| Spec Requirement | Task that implements it |
|---|---|
| Agent loop (while-True) | Task 7 |
| 4 tool schemas with descriptions | Task 3 |
| execute_tool with Python pre-computation | Task 5 |
| MemoryStore load/save/format | Task 4 |
| build_system_prompt with date, memory, rules | Task 6 |
| Memory persists to disk between sessions | Tasks 4, 8 |
| Session 1: 4 turns | Task 8 (SESSIONS dict) |
| Session 2: 1 turn | Task 8 (SESSIONS dict) |
| LLM for extraction (judgment), not arithmetic | Task 8 (_extract_and_save_memory) |
| JSON fallback for markdown-fenced output | Task 8 |
| today's date injected from code | Task 6 |
| Explicit date used as-is; day-only relative to today | Task 6 |
| No agent frameworks | Every task — only `anthropic` SDK |
| Under 300 lines | Checked in Task 10 |
| Transcripts with tool calls visible in logs | Tasks 9, 10 |

**No gaps found.**

---

## JSON Fallback Logic Test (standalone)

This is a one-liner you can run at any time to verify the regex fallback works independently of the API:

```bash
python3 -c "
import re, json
fenced = '\`\`\`json\n{\"summary\": \"test\", \"commitments\": [], \"insights\": []}\n\`\`\`'
match = re.search(r'\{.*\}', fenced, re.DOTALL)
record = json.loads(match.group()) if match else {}
assert record['summary'] == 'test', 'Fallback failed'
print('JSON fallback test PASSED')
"
```
