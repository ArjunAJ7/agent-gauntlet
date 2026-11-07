"""Synthetic document store with ground truth.

A tiny in-memory knowledge base. Tasks seed it with documents; the grader
knows which doc holds the answer, so success is checked deterministically.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DocsStore:
    docs: dict[str, str] = field(default_factory=dict)

    def search(self, query: str) -> list[dict]:
        """Keyword overlap search, like a naive BM25 stand-in."""
        q = {w.lower() for w in query.split() if len(w) > 2}
        hits = []
        for doc_id, text in self.docs.items():
            words = {w.lower().strip(".,;:!?()") for w in text.split()}
            score = len(q & words)
            if score:
                hits.append({"doc_id": doc_id, "score": score,
                             "snippet": text[:120]})
        return sorted(hits, key=lambda h: -h["score"])[:5]

    def read(self, doc_id: str) -> str:
        if doc_id not in self.docs:
            raise KeyError(f"no such document: {doc_id}")
        return self.docs[doc_id]

    def tools_schema(self) -> list[dict]:
        return [
            {"type": "function", "function": {
                "name": "docs_search",
                "description": "Search the document store; returns ranked doc ids with snippets.",
                "parameters": {"type": "object", "properties": {
                    "query": {"type": "string"}}, "required": ["query"]}}},
            {"type": "function", "function": {
                "name": "docs_read",
                "description": "Read one full document by its id.",
                "parameters": {"type": "object", "properties": {
                    "doc_id": {"type": "string"}}, "required": ["doc_id"]}}},
        ]

    def dispatch(self, name: str, args: dict) -> str:
        if name == "docs_search":
            import json
            return json.dumps(self.search(args.get("query", "")))
        if name == "docs_read":
            return self.read(args.get("doc_id", ""))
        raise ValueError(f"unknown tool {name}")
