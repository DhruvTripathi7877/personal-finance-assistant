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


class Agent:
    def __init__(self, memory):
        self.memory = memory
        self.client = anthropic.Anthropic()

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
