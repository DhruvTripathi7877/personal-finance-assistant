import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timedelta

import anthropic
import tools as _tools
from tools import (
    get_recent_transactions,
    get_account_balance,
    get_upcoming_bills,
    set_reminder,
)
from config import USER_PROFILE, SESSION_DATES, TOOL_DEFINITIONS, SESSIONS


def _typewrite(line: str, delay: float = 0.015) -> None:
    for ch in line:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write("\n")
    sys.stdout.flush()


def execute_tool(name: str, args: dict) -> dict:
    _typewrite(f"  \n[TOOL CALL] {name}({args})")

    today = datetime.strptime(SESSION_DATES[_tools.CURRENT_SESSION], "%Y-%m-%d")

    if name == "get_recent_transactions":
        days = args["days"]
        cutoff = today - timedelta(days=days)
        all_txns = get_recent_transactions(days)
        txns = [t for t in all_txns if datetime.strptime(t["date"], "%Y-%m-%d") >= cutoff]
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
        cats = " | ".join(f"{k} ₹{v:,}" for k, v in by_category.items())
        _typewrite(
            f"[TOOL RESULT] {len(txns)} txns — debits ₹{result['total_debits_inr']:,}"
            f" | credits ₹{result['total_credits_inr']:,} | {cats}"
        )
    elif name == "get_account_balance":
        result = get_account_balance()
        summary = " | ".join(f"{k} ₹{v:,}" for k, v in result.items())
        _typewrite(f"[TOOL RESULT] {summary}")
    elif name == "get_upcoming_bills":
        days = args.get("days", 30)
        cutoff = today + timedelta(days=days)
        all_bills = get_upcoming_bills(days)
        bills = [b for b in all_bills if datetime.strptime(b["date"], "%Y-%m-%d") <= cutoff]
        result = {
            "bills": bills,
            "total_due_inr": sum(b["amount"] for b in bills),
        }
        _typewrite(f"[TOOL RESULT] {len(bills)} bills | total due ₹{result['total_due_inr']:,}")
    elif name == "set_reminder":
        result = set_reminder(args["date"], args["content"])
        _typewrite(f"[TOOL RESULT] reminder set for {result['date']}: {args['content']}")
    else:
        result = {"error": f"Unknown tool: {name}"}
        _typewrite(f"[TOOL RESULT] error: unknown tool '{name}'")

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

    def _atomic_write(self, data: dict):
        dir_name = os.path.dirname(os.path.abspath(self.path))
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, suffix=".tmp") as tmp:
            json.dump(data, tmp, indent=2, ensure_ascii=False)
            tmp_path = tmp.name
        os.replace(tmp_path, self.path)

    def save(self, session_record: dict):
        self.data["sessions"].append(session_record)
        self._atomic_write(self.data)
        print(f"  [MEMORY SAVED] {self.path}")

    def reset(self):
        self.data = {"sessions": []}
        self._atomic_write(self.data)
        print(f"  [MEMORY RESET] {self.path}")

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

    def _agent_loop(self, system: str, messages: list, tools: list | None = None) -> str:
        tools = tools if tools is not None else TOOL_DEFINITIONS
        first_text_turn = True
        while True:
            with self.client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=system,
                tools=tools,
                messages=messages,
            ) as stream:
                text_started = False
                for text in stream.text_stream:
                    if not text_started:
                        if first_text_turn:
                            sys.stdout.write("\nAgent: ")
                            first_text_turn = False
                        text_started = True
                    for ch in text:
                        sys.stdout.write(ch)
                        sys.stdout.flush()
                        time.sleep(0.015)
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

    def run_session(self, session_num: int, user_turns: list):
        if session_num == 1:
            self.memory.reset()
        system = build_system_prompt(self.memory, session_num)
        messages = []

        for user_msg in user_turns:
            print(f"\n{'─' * 60}")
            print(f"User: {user_msg}")
            messages.append({"role": "user", "content": user_msg})

            reply = self._agent_loop(system, messages)
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


if __name__ == "__main__":
    session_num = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    memory = MemoryStore()
    agent = Agent(memory)
    agent.run_session(session_num, SESSIONS[session_num])
