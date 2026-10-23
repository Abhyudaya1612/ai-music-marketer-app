"""AI Orchestrator 🧠 — coordinates the five agents, routes structured
data between them, resolves outputs into the final strategy.

Flow (mirrors the architecture diagram):

    SONG → Music Analysis Agent → SongIntelligence
                                        │
              ┌─────────────────────────┼──────────────┐
              ▼                         ▼              ▼
      Audience Intelligence     Content Strategy   (Analytics later)
              │                         │
              └────────────┬────────────┘
                           ▼
                Marketing Strategy Agent
                           │
                           ▼
                Analytics & Optimization Agent
                           │
                           ▼
                AI ORCHESTRATOR → FINAL STRATEGY
"""
from __future__ import annotations
from .schemas import SongInput
from .agents import (MusicAnalysisAgent, AudienceIntelligenceAgent,
                     ContentStrategyAgent, MarketingStrategyAgent,
                     AnalyticsOptimizationAgent)


class MusicMarketerOrchestrator:
    def __init__(self, log_sink: list | None = None):
        self.logs = log_sink if log_sink is not None else []
        self._ = lambda: None
        self.agents = {
            "music": MusicAnalysisAgent(self.logs),
            "audience": AudienceIntelligenceAgent(self.logs),
            "content": ContentStrategyAgent(self.logs),
            "marketing": MarketingStrategyAgent(self.logs),
            "analytics": AnalyticsOptimizationAgent(self.logs),
        }

    def _route(self, frm: str, to: str, payload: str):
        self.logs.append(f"ORCHESTRATOR routes {payload}: {frm} → {to}")

    def run(self, song: SongInput) -> dict:
        self.logs.append(f"STAGE 1: Song → Music Analysis Agent")
        intel = self.agents["music"].run(song)

        self.logs.append("STAGE 2: Orchestrator broadcasts SongIntelligence to specialist agents")
        self._route("MUSIC_ANALYSIS", "AUDIENCE_INTELLIGENCE", "SongIntelligence")
        audience = self.agents["audience"].run(intel)
        self._route("MUSIC_ANALYSIS", "CONTENT_STRATEGY", "SongIntelligence")
        content = self.agents["content"].run(intel, audience)

        self.logs.append("STAGE 3: Aggregated intelligence → Marketing Strategy Agent")
        self._route("ORCHESTRATOR", "MARKETING_STRATEGY",
                    "SongIntelligence + AudienceInsight + ContentPlan")
        strategy = self.agents["marketing"].run(intel, audience, content)

        self.logs.append("STAGE 4: Campaign bundle → Analytics & Optimization Agent")
        self._route("ORCHESTRATOR", "ANALYTICS_OPTIMIZATION", "Strategy bundle (simulated execution)")
        report = self.agents["analytics"].run(intel, audience, content, strategy)

        self.logs.append("STAGE 5: Orchestrator synthesizing FINAL STRATEGY")
        return {
            "song_intelligence": intel,
            "audience": audience,
            "content_plan": content,
            "marketing_strategy": strategy,
            "optimization": report,
            "final": {
                "orchestrator_summary": self._summarize(song, intel, audience, strategy, report),
                "top_priority_actions": self._priorities(intel, audience, strategy, report),
            },
        }

    def _summarize(self, song, intel, audience, strategy, report) -> str:
        return (f"'{song.title}' ({intel.musical_key}, {intel.bpm:.0f} BPM, {intel.mood}) targets "
                f"{audience.primary_segment}. Lead with the hook “{intel.hooks[0]}” on "
                f"{strategy.platform_priority[0]}. Simulated 6-week outcome: score "
                f"{report.metrics.score}/100, {report.metrics.streams:,} streams. "
                f"Next cycle focus: {report.recommendations[0].lower()}.")

    def _priorities(self, intel, audience, strategy, report) -> list[str]:
        return [
            f"Record a 15s hook-first Reel today (“{intel.hooks[0]}”)",
            f"Pitch {strategy.pitch_targets[0]} with A&R angle: {intel.a_r_insights[0]}",
            f"Set up pre-save + budget split: "
            f"{max(strategy.budget_allocation, key=strategy.budget_allocation.get)} first",
            f"Apply Analytics feedback loop: {report.recommendations[0]}",
        ]
