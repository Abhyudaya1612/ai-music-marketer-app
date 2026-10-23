"""Base class for all agents.

Agents are specialized reasoning components. In production they wrap
deterministic systems (Essentia, Librosa, FFmpeg) and ML/LLM models.
Here, deterministic heuristics + seeded simulation stand in so the full
coordination flow runs offline.
"""
from __future__ import annotations


class BaseAgent:
    name: str = "BASE_AGENT"
    emoji: str = "🤖"

    def __init__(self, log_sink: list | None = None):
        # log_sink: shared list the orchestrator collects for the audit trail
        self.log_sink = log_sink if log_sink is not None else []

    def log(self, msg: str):
        self.log_sink.append(f"[{self.emoji} {self.name}] {msg}")

    def run(self, payload):
        raise NotImplementedError
