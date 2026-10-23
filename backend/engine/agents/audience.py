"""Audience Intelligence Agent 👥 — audience hypotheses, demographics, affinity, matching."""
from __future__ import annotations
from ..base import BaseAgent
from ..schemas import SongIntelligence, AudienceInsight, AudienceSegment


class AudienceIntelligenceAgent(BaseAgent):
    name = "AUDIENCE_INTELLIGENCE_AGENT"
    emoji = "👥"

    SEGMENT_LIBRARY = [
        dict(name="Short-form scrollers (18-24)",
             description="Discover music via TikTok/Reels trends; value hooks & relatability",
             age_range="18-24",
             interests=["memes", "fashion", "gaming", "viral trends"],
             platforms={"TikTok": 0.95, "Instagram Reels": 0.85, "YouTube Shorts": 0.8}),
        dict(name="Playlist diggers (25-34)",
             description="Curate personal soundtracks; discover via editorial & algorithmic playlists",
             age_range="25-34",
             interests=["concerts", "vinyl", "coffee culture", "travel"],
             platforms={"Spotify": 0.95, "Apple Music": 0.7, "YouTube": 0.6}),
        dict(name="Nightlife & fitness enthusiasts (21-35)",
             description="High-energy music for workouts, runs, clubs and parties",
             age_range="21-35",
             interests=["fitness", "running", "clubbing", "festivals"],
             platforms={"Spotify": 0.85, "Apple Music": 0.75, "TikTok": 0.6}),
        dict(name="Mood & focus listeners (25-40)",
             description="Lo-fi/chill for work, study and winding down",
             age_range="25-40",
             interests=["productivity", "studying", "wellness", "reading"],
             platforms={"Spotify": 0.9, "YouTube": 0.8, "Apple Music": 0.65}),
        dict(name="Genre loyalists / scene followers (20-38)",
             description="Deep fans of the genre; follow artists, blogs and curators closely",
             age_range="20-38",
             interests=["genre blogs", "small venues", "music discovery", "artist lore"],
             platforms={"Spotify": 0.85, "Instagram": 0.6, "Bandcamp": 0.7}),
    ]

    def run(self, intel: SongIntelligence) -> AudienceInsight:
        self.log("Scoring song against audience segment library ...")
        scored = []
        for seg in self.SEGMENT_LIBRARY:
            scored.append(AudienceSegment(
                name=seg["name"], description=seg["description"],
                age_range=seg["age_range"], interests=seg["interests"],
                platform_affinity=seg["platforms"],
                match_score=round(self._match(intel, seg), 2)))
        scored.sort(key=lambda s: s.match_score, reverse=True)
        insight = AudienceInsight(
            segments=scored, primary_segment=scored[0].name,
            summary=(f"Primary audience: {scored[0].name} (match {scored[0].match_score:.2f}). "
                     f"Secondary: {scored[1].name}."))
        self.log(f"Top segment: {insight.primary_segment}")
        return insight

    def _match(self, intel: SongIntelligence, seg: dict) -> float:
        name = seg["name"].lower()
        score = 0.30
        if "short-form" in name:
            score += 0.25 * intel.energy + (0.20 if intel.hooks else 0)
            score += 0.15 if intel.valence > 0.55 or intel.valence < 0.45 else 0.05
        elif "nightlife" in name or "fitness" in name:
            score += 0.45 if intel.energy > 0.7 else (0.20 if intel.energy > 0.5 else 0.0)
            score += 0.10 if intel.bpm >= 118 else 0.0
        elif "mood" in name or "focus" in name:
            score += 0.45 if intel.energy < 0.45 else 0.05
        elif "playlist diggers" in name:
            score += 0.20 if 0.45 <= intel.valence <= 0.75 else 0.05
            score += 0.15 if intel.energy > 0.5 else 0.05
        elif "genre loyalists" in name:
            score += 0.30 + (0.15 if "nightlife & escape" in intel.lyrical_themes else 0.0)
        if "nightlife & escape" in intel.lyrical_themes:
            score += 0.05
        if "ambition & success" in intel.lyrical_themes and "fitness" in name:
            score += 0.10
        return min(score, 0.99)
