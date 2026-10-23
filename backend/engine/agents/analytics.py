"""Analytics & Optimization Agent 📊 — performance analysis, optimization, learning.

Deterministically simulates campaign performance seeded by the song's own
data. In production this agent pulls real DSP/social APIs; the feedback
contract (OptimizationReport) stays identical.
"""
from __future__ import annotations
import hashlib, random
from ..base import BaseAgent
from ..schemas import (SongIntelligence, AudienceInsight, ContentPlan,
                       MarketingStrategy, PerformanceMetrics, OptimizationReport)


class AnalyticsOptimizationAgent(BaseAgent):
    name = "ANALYTICS_OPTIMIZATION_AGENT"
    emoji = "📊"

    def run(self, intel: SongIntelligence, audience: AudienceInsight,
            content: ContentPlan, strategy: MarketingStrategy) -> OptimizationReport:
        self.log("Simulating 6-week campaign performance against strategy ...")
        seed_src = f"{intel.bpm}{intel.musical_key}{intel.energy}{audience.primary_segment}"
        seed = int(hashlib.md5(seed_src.encode()).hexdigest(), 16) % 10_000
        rng = random.Random(seed)

        strength = (0.45 + 0.25 * intel.energy
                    + 0.20 * audience.segments[0].match_score
                    + 0.10 * min(len(content.pieces) / 5, 1.0))

        streams = int(60_000 + rng.uniform(0.5, 1.6) * 120_000 * strength)
        saves = int(streams * rng.uniform(0.06, 0.12) * strength)
        playlist_adds = int(streams * rng.uniform(0.02, 0.06) * strength)
        social_views = int(streams * rng.uniform(1.5, 4.0) * strength)
        engagement = round(rng.uniform(0.04, 0.09) * strength + 0.03, 4)
        followers = int(social_views * engagement * rng.uniform(0.05, 0.12))
        score = round(min(100, strength * 100 + rng.uniform(-5, 5)), 1)

        metrics = PerformanceMetrics(streams=streams, saves=saves,
            playlist_adds=playlist_adds, social_views=social_views,
            engagement_rate=engagement, follower_delta=followers, score=score)

        worked, under, recs, lessons = [], [], [], []
        if social_views / max(streams, 1) > 2.0:
            worked.append(f"Short-form drove {social_views:,} views — hook-first strategy validated")
        if engagement > 0.07:
            worked.append(f"Strong engagement rate ({engagement:.1%}) — CTA prompts effective")
        if playlist_adds / max(streams, 1) < 0.04:
            under.append("Playlist conversion below target — increase curator outreach volume")
            recs.append("Double pitch targets next cycle; add 20 mid-tier independent curators")
        if intel.energy < 0.5 and audience.segments[0].match_score < 0.6:
            under.append("Song energy may limit short-form virality for primary segment")
            recs.append("Test a sped-up / remix variant for short-form channels")
        recs.append(f"Reallocate budget toward {strategy.platform_priority[0]} (highest audience affinity)")
        lessons.append("Hook within first 15s correlates with Reel completion — keep for next single")
        lessons.append(f"Primary segment ({audience.primary_segment}) responded best — refine lookalike targeting")

        report = OptimizationReport(metrics=metrics,
            what_worked=worked or ["Baseline campaign executed"],
            what_underperformed=under or ["None significant"],
            recommendations=recs, lessons_learned=lessons)
        self.log(f"PerformanceMetrics: score {metrics.score}/100, {streams:,} streams simulated")
        return report
