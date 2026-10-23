"""Marketing Strategy Agent 📢 — release strategy, campaigns, promotion, platform strategy."""
from __future__ import annotations
from ..base import BaseAgent
from ..schemas import SongIntelligence, AudienceInsight, ContentPlan, MarketingStrategy


class MarketingStrategyAgent(BaseAgent):
    name = "MARKETING_STRATEGY_AGENT"
    emoji = "📢"

    def run(self, intel: SongIntelligence, audience: AudienceInsight,
            content: ContentPlan) -> MarketingStrategy:
        self.log("Assembling release plan from intelligence + audience + content inputs ...")
        article = "An" if intel.mood[:1].lower() in "aeiou" else "A"
        strategy = MarketingStrategy(
            release_type="single", timeline_weeks=6,
            phases={
                "Pre-release (W-4 to W-1)": [
                    "Deliver pitch to editorial playlists (Spotify, Apple) 4 weeks out",
                    "Launch pre-save page with teaser short-form content",
                    "Send pre-release to genre curators & music blogs",
                    "Seed 3 teaser Reels/TikToks using the Content Strategy plan",
                ],
                "Release week (W0)": [
                    "Release on all DSPs Friday 00:00 local",
                    "Daily short-form content (per ContentPlan cadence)",
                    "Pitch to New Music Friday / genre editorial lists",
                    "Engage first-hour listeners: reply to every comment",
                ],
                "Post-release (W+1 to W+2)": [
                    "Retarget engagers with paid boosts on best organic Reel",
                    "Release vertical lyric video / visualizer",
                    "Submit to algorithmic playlists (Discover Weekly, Release Radar)",
                ],
                "Sustain (W+3 to W+6)": [
                    "Fan-content challenge using the hook (UGC loop)",
                    "Acoustic/alternate version as momentum follow-up",
                    "Analyze performance → feed results to Analytics Agent",
                ],
            },
            platform_priority=list(audience.segments[0].platform_affinity.keys()),
            budget_allocation={
                "Meta/IG ads (Reels boost)": 40,
                "TikTok Spark Ads": 30,
                "Playlist pitching services": 15,
                "Creator/influencer seeding": 15,
            },
            pitch_targets=[
                "Spotify editorial: genre New Music Friday",
                "Apple Music: genre A-list playlist",
                "Independent genre curators (10-50k followers)",
                "Music blogs accepting premieres",
                "TikTok creator seeding (5 mid-tier creators)",
            ],
            key_message=(f"{article} {intel.mood} {intel.bpm:.0f} BPM track about "
                         f"{intel.lyrical_themes[0] if intel.lyrical_themes else 'the moment'} "
                         f"— built for {audience.primary_segment}."),
        )
        self.log(f"MarketingStrategy ready: {strategy.timeline_weeks}-week plan, "
                 f"top platform = {strategy.platform_priority[0]}")
        return strategy
