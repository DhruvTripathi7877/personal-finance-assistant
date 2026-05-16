# Finance Agent — Design Document

**Date:** 2026-05-15
**Assignment:** AI Engineer Assignment — Finance Companion Agent
**Language:** Python
**Target:** < 300 lines, no agent frameworks

---

## 1. What We Are Building

A finance companion agent for Priya Sharma that runs in two sessions three days apart.

- **Session 1 (Monday, Nov 3):** 4 user turns. Agent helps Priya plan savings, analyze food delivery spending, check if a ₹30,000 house fund commitment is realistic, and sets a reminder.
- **Session 2 (Thursday, Nov 6):** 1 user turn. Priya asks about buying a MacBook. Agent must connect this to the savings plan from Monday, check fresh account data via tools, and give a grounded answer.

The four things Session 2 must demonstrate (from the assignment):
1. **Memory** — remembers the savings plan from Monday
2. **Judgment** — connects MacBook question to that plan on its own
3. **Tool vs. memory discipline** — calls tools for current balance/bills, does not quote stale numbers from memory
4. **Tool action** — calls `set_reminder` where appropriate

---

## 2. What an Agent Is (First Principles)

A regular LLM call: send text in, get text out. One shot.

An agent is different. It is a **loop** where the LLM can pause mid-response, request a tool call, observe the result, and continue thinking. The LLM never executes tools directly — it outputs a structured request ("call `get_account_balance` with no args"). Your code runs the tool and feeds the result back. This continues until the LLM produces a final text response.

```
YOU (your code)            LLM (Claude)
───────────────────────────────────────────
Send messages        →
                     ←   "call get_account_balance()"
Execute tool         →
Send result back     →
                     ←   "call get_upcoming_bills(days=30)"
Execute tool         →
Send result back     →
                     ←   Final response text
```

The loop in pseudocode:

```python
messages = [system_prompt, user_message]

while True:
    response = claude.call(messages, tools=available_tools)

    if response wants to call a tool:
        result = execute_that_tool(response.tool_name, response.args)
        messages.append(tool_result)
        # continue — LLM hasn't finished thinking
    else:
        print(response.text)
        break
```

Everything else — memory, prompts, session management — is built around this core loop.

---

## 3. File Structure

```
your-agent/
├── tools.py        # provided — do not modify
├── sessions.md     # provided — do not modify
├── agent.py        # the entire agent (~250 lines)
└── memory.json     # auto-created at runtime after Session 1
```

**Why one file?** The assignment rewards simplicity and staying under 300 lines. Splitting into multiple files adds import boilerplate without adding clarity. One file is also easier to walk through in the Loom recording.

---

## 4. Components Inside `agent.py`

```
agent.py
├── TOOL_DEFINITIONS       — JSON schemas that tell Claude what tools exist
├── execute_tool()         — dispatches Claude's tool requests to tools.py
├── MemoryStore class      — reads/writes memory.json
├── build_system_prompt()  — assembles Claude's instructions + memory context
└── Agent class            — runs the loop, orchestrates everything
```

Mapping to Java concepts (for orientation):
- `MemoryStore` = a DAO for `memory.json`
- `Agent` = a Service class coordinating LLM, tools, and memory
- `TOOL_DEFINITIONS` = a schema registry
- `execute_tool()` = a dispatcher/router
- `build_system_prompt()` = a template builder

---

## 5. Tool Definitions

Claude doesn't know about `tools.py` automatically. We register each tool as a JSON schema. Claude reads these schemas and decides when to call each one.

```python
TOOL_DEFINITIONS = [
    {
        "name": "get_recent_transactions",
        "description": "Get user's transactions from the last N days. Use this to analyze spending patterns or check recent activity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "How many days back to fetch"}
            },
            "required": ["days"]
        }
    },
    {
        "name": "get_account_balance",
        "description": "Get current account balances. Always call this for up-to-date numbers — never use remembered balances.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_upcoming_bills",
        "description": "Get bills due in the next N days.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "How many days ahead to look"}
            },
            "required": ["days"]
        }
    },
    {
        "name": "set_reminder",
        "description": "Set a reminder for the user on a specific date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                "content": {"type": "string", "description": "What to remind the user"}
            },
            "required": ["date", "content"]
        }
    }
]
```

**Design decision — description wording matters:** `get_account_balance` says "Always call this — never use remembered balances." This is prompt engineering embedded in the schema. It directly enforces the assignment's tool vs. memory discipline requirement without extra code.

---

## 6. `execute_tool()` — The Dispatcher

When Claude says "call `get_account_balance`", your code receives a tool name (string) and arguments (dict). This function routes that to the actual function in `tools.py`.

```python
def execute_tool(name: str, args: dict):
    print(f"  [TOOL CALL] {name}({args})")    # visible in logs

    if name == "get_recent_transactions":
        txns = get_recent_transactions(args["days"])
        # arithmetic in Python — assignment flags using LLM to sum/parse
        by_category = {}
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
            "total_due_inr": sum(b["amount"] for b in bills),  # pre-summed in Python
        }
    elif name == "set_reminder":
        result = set_reminder(args["date"], args["content"])
    else:
        result = {"error": f"Unknown tool: {name}"}

    print(f"  [TOOL RESULT] {json.dumps(result)}\n")  # visible in logs
    return result
```

**Why print here?** The assignment requires tool calls and results to be visible in logs. Putting the print inside `execute_tool()` means every tool call anywhere in the agent gets logged automatically.

**Why not use `TOOLS[name](**args)` from tools.py?** The provided functions take positional arguments, not keyword arguments. Explicit if/elif is safer and explicit about argument mapping.

**Why pre-compute sums here?** The assignment explicitly flags using an LLM to do arithmetic ("sum a column"). We compute `category_totals_inr` and `total_due_inr` in Python and hand Claude the pre-computed numbers. Claude then uses those numbers to reason ("food delivery was ₹10,640 — that's 8.9% of your income"), but it never calculates them. Clean split: code does math, LLM does judgment.

---

## 7. Memory Layer — What We Store and Why

Memory is not "everything from Session 1." It is **durable truths about this user** — things still true three days later that are worth knowing before Priya says anything in Session 2.

### MemoryStore Class

```python
class MemoryStore:
    def __init__(self, path="memory.json"):
        self.path = path
        self.data = self._load()

    def _load(self):
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

### What Goes Into `memory.json` After Session 1

```json
{
  "sessions": [
    {
      "session_id": 1,
      "date": "2025-11-03",
      "summary": "User committed to saving ₹30,000 for house fund this month. Concerned about food delivery overspending.",
      "commitments": [
        "Transfer ₹30,000 to house_fund on 2025-11-25"
      ],
      "insights": [
        "Food delivery spend last month (Oct): ~₹10,640. User wants to cut in half (~₹5,300 target).",
        "Longer-term goal: ₹15 lakh for house down payment in 2 years."
      ],
      "reminders_set": [
        {"date": "2025-11-25", "content": "Transfer ₹30,000 to house fund"}
      ]
    }
  ]
}
```

### What We Deliberately Do NOT Store

| Do Not Store | Why |
|---|---|
| Account balances (`checking: 128000`) | Rent (₹25,000) gets paid between sessions — number is stale |
| Transaction list | Always fetch fresh; 30-day window shifts |
| Upcoming bills detail | Some will have been paid by Session 2 |

**Why this matters for Session 2:** When Priya asks about the MacBook, Claude sees the ₹30,000 commitment in memory, then calls `get_account_balance()` and gets ₹99,820 (not ₹1,28,000 — rent was paid). It calls `get_upcoming_bills()` and sees ₹21,500 still coming. Real math: ₹99,820 − ₹21,500 − ₹30,000 commitment = ₹48,320 truly available. MacBook costs ₹80,000. That's a real, grounded answer — not one based on stale memory.

---

## 8. System Prompt — Claude's Instructions

```python
USER_PROFILE = {
    "name": "Priya Sharma",
    "age": 28,
    "city": "Bangalore",
    "monthly_income_inr": 120000,
    "stated_goal": "Save ₹15 lakh in 2 years for a house down payment in Bangalore",
}

SESSION_DATES = {1: "2025-11-03", 2: "2025-11-06"}

def build_system_prompt(memory: MemoryStore, session_num: int) -> str:
    from datetime import datetime
    today = SESSION_DATES[session_num]
    month_year = datetime.strptime(today, "%Y-%m-%d").strftime("%B %Y")  # "November 2025"
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

**Why inject memory into the system prompt (not the conversation)?**
The system prompt defines who Claude IS at the start of every session. Memory is background knowledge the agent genuinely has — not something being narrated to it mid-conversation. Injecting it as a user message ("here's what happened last time") would look unnatural.

**Why `TODAY'S DATE` and the explicit month?** Claude has no clock and no real-time date access. Its implicit sense of "now" comes from training data — which has a cutoff in mid-2025, making its default "current date" unreliable. This creates a concrete non-determinism risk: the assignment's scenario is November 2025, but this code runs in May 2026. Without an explicit anchor, when Priya says "remind me on the 25th", Claude might produce `2025-11-25` one run and `2026-05-25` the next — depending on how it weighs the conversation's context clues vs. its implicit training-time "now". The `set_reminder` call would silently get the wrong date.

The fix has two parts: (1) inject the exact ISO date from `SESSION_DATES` — a code constant, not inferred by LLM — so Claude has an unambiguous anchor. (2) derive the human-readable month/year in Python (`datetime.strptime`) and include the explicit instruction "do not guess based on the current real-world date." Claude's system prompt is its highest-priority context — it overrides implicit training assumptions completely.

**Why Rule 4 (use pre-computed totals)?** We sum transactions in Python in `execute_tool()`. Rule 4 tells Claude to trust those pre-computed numbers rather than attempting its own arithmetic — reinforcing the code-does-math / LLM-does-judgment split.

**Why Rules 1 and 2 together?** They are the two sides of tool vs. memory discipline. Rule 1 handles dynamic data (always fetch fresh). Rule 2 handles durable data (use what you know). Being explicit in the prompt means Claude follows this without engineering it into every interaction.

---

## 9. The Agent Loop — Core Implementation

```python
import anthropic

class Agent:
    def __init__(self, memory: MemoryStore):
        self.memory = memory
        self.client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    def _agent_loop(self, system: str, messages: list) -> str:
        """Run Claude until it produces a final text response (possibly after tool calls)."""
        while True:
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=system,
                tools=TOOL_DEFINITIONS,
                messages=messages
            )

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result)
                        })
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user",      "content": tool_results})
                # loop — Claude sees results and continues thinking

            else:
                # stop_reason == "end_turn"
                for block in response.content:
                    if hasattr(block, "text"):
                        return block.text

    def run_session(self, session_num: int, user_turns: list):
        system = build_system_prompt(self.memory, session_num)
        messages = []

        for user_msg in user_turns:
            print(f"\n{'─'*60}")
            print(f"User: {user_msg}")
            messages.append({"role": "user", "content": user_msg})

            reply = self._agent_loop(system, messages)
            messages.append({"role": "assistant", "content": reply})
            print(f"Agent: {reply}")

        if session_num == 1:
            self._extract_and_save_memory(session_num, messages)
```

### What Happens in Session 2 (MacBook question), Step by Step

```
1. messages = [{"role": "user", "content": "my colleague is selling his MacBook..."}]

2. Call Claude → stop_reason = "tool_use"
   Claude: call get_account_balance()

3. execute_tool() → {"checking": 99820, "savings": 145000, ...}
   Append to messages, loop

4. Call Claude → stop_reason = "tool_use"
   Claude: call get_upcoming_bills(days=30)

5. execute_tool() → [SIP ₹10,000, Internet ₹3,500, Credit card ₹8,000]
   Append to messages, loop

6. Call Claude → stop_reason = "tool_use"
   Claude: call set_reminder(date="2025-11-25", content="Review MacBook purchase decision")

7. execute_tool() → {"status": "set", "reminder_id": "rem_1234", ...}
   Append to messages, loop

8. Call Claude → stop_reason = "end_turn"
   Claude: "The MacBook is ₹80,000 and your checking is ₹99,820, but rent
   has already been paid. You still have ₹21,500 in bills coming and you
   committed to ₹30,000 for your house fund on the 25th..."

9. Return text. Done.
```

---

## 10. Memory Extraction After Session 1

```python
    def _extract_and_save_memory(self, session_num: int, messages: list):
        # Strip tool-call machinery — extraction model only needs readable text
        clean = []
        for msg in messages:
            content = msg["content"]
            if isinstance(content, str):
                clean.append({"role": msg["role"], "content": content})
            elif isinstance(content, list):
                text_parts = [b.text for b in content if hasattr(b, "text")]
                if text_parts:
                    clean.append({"role": msg["role"], "content": " ".join(text_parts)})

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
            messages=messages
        )

        raw = response.content[0].text
        try:
            record = json.loads(raw)
        except json.JSONDecodeError:
            # Claude sometimes wraps JSON in markdown fences — strip and retry
            import re
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            record = json.loads(match.group()) if match else {
                "summary": "Session completed.",
                "commitments": [],
                "insights": []
            }

        record["session_id"] = session_num
        record["date"] = SESSION_DATES[session_num]

        self.memory.save(record)
        print(f"\n[MEMORY] Saved: {json.dumps(record, indent=2)}")
```

**Why use an LLM for extraction?** Deciding *what is worth remembering* from a conversation is a judgment call — exactly what LLMs are good at. The alternative (regex-matching for numbers and dates) would be brittle. The extraction prompt is tightly constrained: fixed JSON shape, explicit exclusions (no balances), so the LLM has little room to hallucinate.

**Why a JSON parse fallback?** Claude occasionally wraps JSON output in markdown code fences (` ```json ... ``` `). `json.loads()` would fail on that. The fallback strips fences with a regex and retries. If that also fails, we store a safe empty record — the agent stays running and the session isn't lost.

---

## 11. Entry Point

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
    ]
}

if __name__ == "__main__":
    import sys
    session_num = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    memory = MemoryStore()
    agent = Agent(memory)
    agent.run_session(session_num, SESSIONS[session_num])
```

**How to run:**
```bash
# Step 1: ensure CURRENT_SESSION = 1 in tools.py
python agent.py 1

# Step 2: flip CURRENT_SESSION = 2 in tools.py, then:
python agent.py 2
```

---

## 12. Assignment Requirements Coverage

| Requirement | Implementation |
|---|---|
| Memory — remembers savings plan | `memory.json` has the ₹30,000 commitment; injected into system prompt at Session 2 start |
| Judgment — connects MacBook to plan | System prompt Rule 3 ("check if new question connects to existing commitments"). Claude does this with no extra code. |
| Tool discipline — checks fresh balance | Tool description says "never use remembered balances." Claude calls `get_account_balance()` before answering. |
| Tool action — calls `set_reminder` | Tool is registered; Claude decides when a reminder is contextually appropriate. |
| No agent frameworks | Pure Anthropic SDK + stdlib only |
| Memory persists to disk | `memory.json` written after Session 1 via `MemoryStore.save()` |
| LLM only where judgment needed | Arithmetic done in code. LLM used for: responding, deciding which tools to call, extracting memory. |
| Under 300 lines | Estimated ~250 lines |

---

## 13. Open Questions / Things to Refine

- [x] Should memory extraction happen after every session (including Session 2) or only Session 1? → **Only after sessions that have meaningful new commitments. Session 2 is one turn — not worth extracting separately. Revisit if sessions grow.**
- [x] Should we add a `today` date to the system prompt? → **Yes, added. `SESSION_DATES` dict maps session number to ISO date.**
- [x] Error handling for `json.loads()` on memory extraction output? → **Added: regex fallback to strip markdown fences, then safe empty-record fallback.**
- [x] Model choice? → **`claude-sonnet-4-6` for main agent (capable reasoning), `claude-haiku-4-5-20251001` for memory extraction (cheap, constrained task).**
- [x] Arithmetic in Python or LLM? → **Python. `execute_tool()` pre-computes `category_totals_inr` and `total_due_inr`. System prompt Rule 4 tells Claude to use those directly.**
