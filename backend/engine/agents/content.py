"""Content Strategy Agent 🎬 — Reels, Shorts, hooks, concepts, captions, formats."""
from __future__ import annotations
from ..base import BaseAgent
from ..schemas import SongIntelligence, AudienceInsight, ContentPlan, ContentPiece


class ContentStrategyAgent(BaseAgent):
    name = "CONTENT_STRATEGY_AGENT"
    emoji = "🎬"

    def run(self, intel: SongIntelligence, audience: AudienceInsight) -> ContentPlan:
        self.log(f"Building content plan for primary segment: {audience.primary_segment}")
        hook_line = intel.hooks[0] if intel.hooks else "the chorus drop"
        pieces = [
            ContentPiece(
                format="Reel / TikTok",
                hook=f"POV: {hook_line}",
                concept="Cinematic night-drive visuals cut on the beat drop; text overlay reveals the hook line word by word",
                caption=f"this one hits different after midnight 🌃",
                cta="Pre-save / follow for release day",
                sound_strategy=f"Start at the pre-chorus, drop into chorus ({intel.bpm:.0f} BPM grid)"),
            ContentPiece(
                format="Short (behind-the-scenes)",
                hook="How this song was made in 30 seconds",
                concept="Split-screen: demo sketch vs final production, timestamped to the hook",
                caption="from voice memo to this. full song friday 🎧",
                cta="Comment '🎧' and we'll DM you the pre-save",
                sound_strategy="Chorus hook looped under the whole Short"),
            ContentPiece(
                format="Story sequence (5 frames)",
                hook="Lyric reveal",
                concept="One lyric per story frame, stylized type over grainy footage; final frame = pre-save link sticker",
                caption="day 3 of telling you about this song",
                cta="Swipe up / link sticker to pre-save",
                sound_strategy="Isolated vocal hook (a cappella snippet)"),
            ContentPiece(
                format="Carousel / Post",
                hook="The story behind the song",
                concept="6-slide mini-narrative: inspiration → writing → production → meaning; ends with release info",
                caption="about this song — read till the last slide.",
                cta="Share to your story if this resonates",
                sound_strategy="Static post; link in bio to teaser"),
            ContentPiece(
                format="TikTok trend-rider",
                hook=f"Using the {intel.mood.split(',')[0].strip()} sound trend",
                concept="Adapt the current trending format (transition/glow-up) but soundtracked with our hook instead",
                caption="we heard this trend needed a better soundtrack 👀",
                cta="Use this sound — link in comments",
                sound_strategy="Hook loop, 15s cut for re-usability"),
        ]
        plan = ContentPlan(
            pieces=pieces,
            posting_cadence=("5 posts/week pre-release (teasers + story), "
                             "daily short-form during release week, "
                             "3 posts/week post-release (UGC + live clips)"),
            overarching_angle=(f"Position the '{hook_line}' hook as a relatable moment for "
                               f"{audience.primary_segment}."))
        self.log(f"ContentPlan ready: {len(pieces)} pieces")
        return plan
