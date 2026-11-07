"""Synthetic ticket tracker with ground truth.

Tickets are dicts; tools list/filter and read them. Tasks ask questions whose
answers require combining fields across tickets; the grader knows the truth.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class TicketTracker:
    tickets: list[dict] = field(default_factory=list)

    def list_tickets(self, status: str | None = None) -> list[dict]:
        out = [{"id": t["id"], "title": t["title"], "status": t["status"],
                "assignee": t["assignee"], "priority": t["priority"]}
               for t in self.tickets if status is None or t["status"] == status]
        return out

    def read_ticket(self, ticket_id: str) -> dict:
        for t in self.tickets:
            if t["id"] == ticket_id:
                return t
        raise KeyError(f"no such ticket: {ticket_id}")

    def tools_schema(self) -> list[dict]:
        return [
            {"type": "function", "function": {
                "name": "tickets_list",
                "description": "List tickets (id, title, status, assignee, priority). Optional status filter.",
                "parameters": {"type": "object", "properties": {
                    "status": {"type": "string", "enum": ["open", "closed"]}}, "required": []}}},
            {"type": "function", "function": {
                "name": "tickets_read",
                "description": "Read one full ticket by id, including its notes.",
                "parameters": {"type": "object", "properties": {
                    "ticket_id": {"type": "string"}}, "required": ["ticket_id"]}}},
        ]

    def dispatch(self, name: str, args: dict) -> str:
        if name == "tickets_list":
            return json.dumps(self.list_tickets(args.get("status") or None))
        if name == "tickets_read":
            return json.dumps(self.read_ticket(args.get("ticket_id", "")))
        raise ValueError(f"unknown tool {name}")
