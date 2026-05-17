# Personal Finance Assistant

A finance companion agent that holds two conversations with the same user three days apart, demonstrating memory persistence, tool calling, and judgment across sessions.

---

## Prerequisites

- Python 3.11+
- An Anthropic API key — get one at [console.anthropic.com](https://console.anthropic.com)

---

## Setup

```bash
# Clone the repo
git clone https://github.com/DhruvTripathi7877/personal-finance-assistant.git
cd personal-finance-assistant

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install anthropic pytest

# Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## Running the agent

**Step 1 — Run Session 1**

Ensure `CURRENT_SESSION = 1` in `tools.py` (it is by default), then:

```bash
python agent.py 1
```

This runs 4 user turns and writes `memory.json` at the end.

**Step 2 — Flip the session**

Open `tools.py` and change line 12 to:

```python
CURRENT_SESSION = 2
```

**Step 3 — Run Session 2**

```bash
python agent.py 2
```

The agent loads `memory.json` from Session 1 and uses it to answer Priya's MacBook question with full context.

---

## Running tests

```bash
pytest test_agent.py -v
```

14 unit tests covering `MemoryStore`, `execute_tool`, and `build_system_prompt`.

---

## Project structure

```
├── agent.py               # Core agent — loop, memory, prompt, tool dispatch
├── config.py              # Static config — user profile, tool schemas, session turns
├── tools.py               # Mock tool implementations (provided, do not modify)
├── sessions.md            # Exact user messages for both sessions (provided)
├── test_agent.py          # Unit tests
├── memory.json            # Persisted memory written after Session 1
├── session1_transcript.txt
└── session2_transcript.txt
```
