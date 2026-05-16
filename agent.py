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
