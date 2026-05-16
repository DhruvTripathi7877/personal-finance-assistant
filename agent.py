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

    print(f"  [TOOL RESULT] {json.dumps(result, ensure_ascii=False)}\n")
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
            json.dump(self.data, f, indent=2, ensure_ascii=False)
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
4. Tool results include pre-computed totals (category_totals_inr, total_due_inr, total_debits_inr). When reporting any spending figure, quote these exact numbers — never approximate, round, or re-derive them yourself.
5. Response format: state your recommendation clearly, then justify it using specific numbers from tools and the user's commitments from memory. One to two paragraphs.
"""


class Agent:
    def __init__(self, memory):
        self.memory = memory
        self.client = anthropic.Anthropic()
        self._analysis_tools = [t for t in TOOL_DEFINITIONS if t["name"] != "set_reminder"]
        self._reminder_tools = [t for t in TOOL_DEFINITIONS if t["name"] == "set_reminder"]

    def _agent_loop(self, system: str, messages: list, tools: list | None = None) -> str:
        tools = tools if tools is not None else TOOL_DEFINITIONS
        printed_header = False
        while True:
            with self.client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=system,
                tools=tools,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    if not printed_header:
                        print("\nAgent: ", end="", flush=True)
                        printed_header = True
                    print(text, end="", flush=True)
                response = stream.get_final_message()

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, ensure_ascii=False),
                        })
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

            else:
                print()  # newline after streamed text
                return next(b.text for b in response.content if hasattr(b, "text"))

    def _proactive_reminder(self, system: str, messages: list) -> str | None:
        check_msgs = messages + [{"role": "user", "content": (
            "Review your last response. If you advised the user to defer a decision to a "
            "specific future time (e.g. 'revisit in January', 'wait a couple months', "
            "'check back in December'), set a reminder for that date using set_reminder. "
            "If your response contained no time-based deferral, say 'No reminders needed.'"
        )}]
        resp = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            system=system,
            tools=self._reminder_tools,
            messages=check_msgs,
        )
        if resp.stop_reason == "tool_use":
            for block in resp.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input)
                    if result.get("status") == "set":
                        return result["date"]
        return None

    def run_session(self, session_num: int, user_turns: list):
        system = build_system_prompt(self.memory, session_num)
        messages = []

        for user_msg in user_turns:
            print(f"\n{'─' * 60}")
            print(f"User: {user_msg}")
            messages.append({"role": "user", "content": user_msg})

            reply = self._agent_loop(system, messages,
                                      tools=self._analysis_tools if session_num > 1 else None)
            if session_num > 1:
                reminder_date = self._proactive_reminder(system, messages + [{"role": "assistant", "content": reply}])
                if reminder_date:
                    suffix = f"\n\nI've set a reminder for {reminder_date} to follow up on this."
                    print(suffix, end="")
                    reply += suffix
            messages.append({"role": "assistant", "content": reply})

        if session_num == 1:
            self._extract_and_save_memory(session_num, messages)

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
        # API requires conversation to end with a user turn
        clean.append({"role": "user", "content": "Extract the memory as instructed."})

        extraction_prompt = """From this conversation, extract exactly:
1. A one-sentence summary of what happened
2. Commitments the USER THEMSELVES explicitly made (amounts, dates, actions they agreed to) — do NOT include suggestions the agent made that the user did not clearly accept
3. Key financial insights worth remembering (spending patterns, goals the user stated) as a list — use only facts from the data, not agent recommendations

Return ONLY valid JSON in this shape:
{"summary": "...", "commitments": ["..."], "insights": ["..."]}

Do NOT include balances or transaction amounts — those will be fetched fresh next session.
Do NOT include agent-suggested targets or caps unless the user explicitly agreed to them."""

        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=extraction_prompt,
            messages=clean,
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
        print(f"\n[MEMORY] Saved: {json.dumps(record, indent=2, ensure_ascii=False)}")


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
