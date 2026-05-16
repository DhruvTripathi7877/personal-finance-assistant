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
