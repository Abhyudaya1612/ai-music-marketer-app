"""Campaign planner service with Ollama integration and fallback templates."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

from ..config import settings
from ..domain.models import StudioSong

logger = logging.getLogger(__name__)


def check_ollama_available() -> bool:
    """Check if Ollama is available via HTTP health check."""
    if not settings.ollama_enabled:
        logger.info("Ollama disabled in config")
        return False
    
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{settings.ollama_base_url}/api/tags")
            response.raise_for_status()
            return True
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        logger.warning(f"Ollama unavailable: {e}")
        return False
    except Exception as e:
        logger.warning(f"Unexpected error checking Ollama: {e}")
        return False


def _call_ollama(prompt: str, max_retries: int = 1) -> dict[str, Any] | None:
    """
    Call Ollama API with JSON extraction. Retry once on parse failure.
    
    Returns parsed JSON dict or None if failed.
    """
    if not settings.ollama_enabled:
        return None
    
    for attempt in range(max_retries + 1):
        try:
            with httpx.Client(timeout=settings.ollama_timeout_seconds) as client:
                response = client.post(
                    f"{settings.ollama_base_url}/api/generate",
                    json={
                        "model": settings.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                    },
                )
                response.raise_for_status()
                data = response.json()
                response_text = data.get("response", "").strip()
                
                # Clean markdown code blocks if present
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                elif response_text.startswith("```"):
                    response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                
                response_text = response_text.strip()
                
                # Try to parse JSON
                try:
                    parsed = json.loads(response_text)
                    logger.info(f"Ollama call successful on attempt {attempt + 1}")
                    return parsed
                except json.JSONDecodeError as e:
                    logger.warning(f"Ollama returned invalid JSON (attempt {attempt + 1}): {e}")
                    if attempt < max_retries:
                        continue
                    return None
        
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning(f"Ollama connection failed (attempt {attempt + 1}): {e}")
            if attempt < max_retries:
                continue
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling Ollama (attempt {attempt + 1}): {e}")
            if attempt < max_retries:
                continue
            return None
    
    return None


def generate_song_quality_report(
    intelligence_json: dict[str, Any] | None,
    song: StudioSong,
) -> dict[str, Any]:
    """Generate song quality assessment via Ollama or fallback."""
    
    prompt = f"""Analyze this song for commercial potential and quality indicators:

Song Title: {song.title}
Artist: {song.artist_name or 'Unknown'}
Genre: {song.genre_preferences[0] if song.genre_preferences else 'Unknown'}

Based on available data, provide an objective assessment (not guaranteed predictions):

Respond with ONLY valid JSON (no markdown, no explanations):
{{
  "score": (integer 1-10 indicating production quality and commercial appeal),
  "strengths": (list of 3-5 key strengths, e.g., "Strong hook", "Professional production"),
  "weaknesses": (list of 2-4 areas for improvement, e.g., "Vocals could be mixed higher"),
  "audience_hypotheses": (list of 3-4 potential audience segments),
  "genre_positioning": (string describing genre positioning and closest comparable artists),
  "commercial_observations": (string with honest assessment of marketability, NOT guarantees)
}}

IMPORTANT: Label AI content with 'AI Assessment:' prefix. Never guarantee streaming numbers or virality.
Only include observations that are defensible based on the genre and song characteristics."""

    ollama_result = _call_ollama(prompt)
    
    if ollama_result:
        # Validate expected keys
        required_keys = {"score", "strengths", "weaknesses", "audience_hypotheses", "genre_positioning", "commercial_observations"}
        if all(k in ollama_result for k in required_keys):
            logger.info("Using Ollama song quality report")
            # Mark as AI assessment
            for key in ["commercial_observations", "genre_positioning"]:
                if key in ollama_result and not ollama_result[key].startswith("AI Assessment:"):
                    ollama_result[key] = f"AI Assessment: {ollama_result[key]}"
            return ollama_result
    
    # Fallback template
    logger.info("Using fallback song quality report template")
    return {
        "score": 7,
        "strengths": [
            "Potential for strong listener connection based on genre",
            "Multiple promotional angles available",
            "Suitable for social media platforms",
        ],
        "weaknesses": [
            "Commercial success depends heavily on marketing strategy",
            "Audience discovery is competitive",
        ],
        "audience_hypotheses": [
            "Fans of similar genre and style",
            "Playlist curators targeting this sound",
            "Social media creators in relevant niches",
        ],
        "genre_positioning": "Positioned within the broader indie/pop landscape with potential for cross-genre appeal",
        "commercial_observations": "AI Assessment: Song has typical commercial potential for its genre. Success depends on effective marketing and audience connection. No guaranteed streaming numbers or virality.",
    }


def generate_campaign_plan(
    intelligence_json: dict[str, Any] | None,
    song: StudioSong,
    budget: float,
    goals: list[str] | None,
    target_audience: str | None,
    release_date: date | None,
) -> dict[str, Any]:
    """Generate pre-release, release-week, and post-release campaign tactics."""
    
    target_audience_str = target_audience or "General audience interested in the artist's genre"
    release_date_str = release_date.isoformat() if release_date else "TBD"
    
    prompt = f"""Create a practical marketing campaign timeline for this song:

Song: {song.title} by {song.artist_name or 'Unknown'}
Genre: {song.genre_preferences[0] if song.genre_preferences else 'Unknown'}
Release Date: {release_date_str}
Budget: ${budget}
Target Audience: {target_audience_str}
Goals: {', '.join(goals) if goals else 'Build awareness and streaming'}

Provide specific, actionable tactics organized by phase. Respond with ONLY valid JSON:
{{
  "pre_release": (list of 3-5 tactics for 2-4 weeks before release),
  "release_week": (list of 5-7 tactics for the release week, emphasizing momentum),
  "post_release": (list of 4-6 tactics for the weeks after release),
  "campaign_objectives": (list of 3-4 measurable objectives),
  "kpis": (list of 4-6 key performance indicators),
  "content_pillars": (list of 3-4 content themes to organize social posts),
  "positioning_usp": (string describing unique positioning for this song)
}}

Keep tactics specific and implementable. Each tactic should be a string description."""

    ollama_result = _call_ollama(prompt)
    
    if ollama_result:
        required_keys = {"pre_release", "release_week", "post_release", "campaign_objectives", "kpis", "content_pillars", "positioning_usp"}
        if all(k in ollama_result for k in required_keys):
            logger.info("Using Ollama campaign plan")
            return ollama_result
    
    # Fallback template
    logger.info("Using fallback campaign plan template")
    return {
        "pre_release": [
            "Announce release date and post teaser clips",
            "Build anticipation with behind-the-scenes content",
            "Reach out to playlist curators in the genre",
            "Create pre-save links on streaming platforms",
        ],
        "release_week": [
            "Release the official song across all platforms",
            "Publish music video or lyric video if available",
            "Post release announcement on all social channels",
            "Go live on TikTok or Instagram to celebrate",
            "Send thank you messages to early listeners",
            "Engage with all comments and messages",
            "Post daily content tie-ins (polls, Q&A, clips)",
        ],
        "post_release": [
            "Share listener testimonials and reactions",
            "Release alternate versions or remixes",
            "Post content featuring the song on social media",
            "Thank playlist curators who added the song",
            "Analyze performance and plan next release",
            "Maintain momentum with bonus content",
        ],
        "campaign_objectives": [
            "Maximize initial streaming and listener acquisition",
            "Build engaged community around the song",
            "Establish artist presence across platforms",
            "Generate social media momentum and reach",
        ],
        "kpis": [
            "Total streams in first 30 days",
            "New monthly listeners gained",
            "Playlist placements and reach",
            "Social media engagement rate and followers",
            "Website or link clicks from promotion",
            "Listener retention rate (repeat plays)",
        ],
        "content_pillars": [
            "Behind-the-scenes creation story",
            "Artist personality and lifestyle",
            "Song production and technical details",
            "Audience connection and engagement",
        ],
        "positioning_usp": "A fresh take on the genre with authentic artist voice and relatable themes",
    }


def generate_captions_and_concepts(
    intelligence_json: dict[str, Any] | None,
    song: StudioSong,
    target_platforms: list[str] | None,
) -> dict[str, Any]:
    """Generate captions, video concepts, hooks, and hashtags."""
    
    platforms_str = ", ".join(target_platforms) if target_platforms else "Instagram, TikTok, YouTube, Twitter"
    
    prompt = f"""Generate social media content for this song:

Song: {song.title} by {song.artist_name or 'Unknown'}
Platforms: {platforms_str}

Create at least 10 captions for each platform and 10 short-form video concepts.
Respond with ONLY valid JSON:
{{
  "instagram_captions": (list of 10+ captions suitable for Reels),
  "tiktok_captions": (list of 10+ captions for TikTok videos),
  "twitter_captions": (list of 10+ captions for Twitter/X posts),
  "video_concepts": (list of 10+ objects with: title, description, hook (opening line), platform, visual_direction),
  "hashtags": (list of 15-25 relevant hashtags),
  "cta_examples": (list of 5-7 call-to-action examples)
}}

Make captions authentic and engaging. Avoid generic suggestions. Include emojis where appropriate.
Hooks should be compelling opening lines to grab attention in the first 1-3 seconds."""

    ollama_result = _call_ollama(prompt)
    
    if ollama_result:
        required_keys = {"instagram_captions", "tiktok_captions", "twitter_captions", "video_concepts", "hashtags", "cta_examples"}
        # Verify minimum counts
        if all(k in ollama_result for k in required_keys):
            if (len(ollama_result.get("instagram_captions", [])) >= 10 and
                len(ollama_result.get("tiktok_captions", [])) >= 10 and
                len(ollama_result.get("video_concepts", [])) >= 10):
                logger.info("Using Ollama captions and concepts")
                return ollama_result
    
    # Fallback template
    logger.info("Using fallback captions and concepts template")
    return {
        "instagram_captions": [
            f"New song alert 🎵 {song.title} is here. What do you think?",
            f"Poured my heart into {song.title}. Out now everywhere 💫",
            f"This one's been sitting in my soul for a while... {song.title} is finally here 🎧",
            "Reels unlocked. New music unlocked. 🔓",
            f"{song.title} - the song I didn't know I needed to make",
            "If you only listen to one new song this week, make it this one 👀",
            "Production mood: obsessed. That's all.",
            "Genre-bending energy on this one ⚡",
            "Your new favorite song just dropped 🚀",
            "Made this late at night when the ideas hit different 🌙",
            f"Stream {song.title} everywhere music is played",
            "The lyrics, the production, the vibes... all there. Link in bio 🔗",
        ],
        "tiktok_captions": [
            f"POV: You just discovered your new favorite song",
            f"The song that made me finally hit post 🎬",
            f"Which part is stuck in YOUR head? 🎵",
            f"New song. New energy. {song.title} out now",
            f"This beat won't leave my head (literally made it)",
            f"Show me your dance to this ⬇️",
            f"Best song I've made so far? Maybe 👀",
            f"The production on this one > expectations",
            f"If you vibe with {song.title}, follow for more 🎧",
            f"Made this in the studio yesterday. Posted today. Zero regrets.",
            f"Try making a video to this 🎬",
            f"Your summer anthem might be dropping soon 👀",
        ],
        "twitter_captions": [
            f"🚨 {song.title} is officially out 🎵",
            f"New music: {song.title} — fresh, authentic, and ready to rock your feed",
            f"After weeks of studio sessions, {song.title} is finally here ✨",
            f"Stream {song.title} on Spotify, Apple Music, YouTube, and everywhere",
            "Just released the song I'm most proud of so far",
            f"The {song.genre_preferences[0] if song.genre_preferences else 'indie'} community is about to go crazy for this one",
            "Tag someone who needs to hear this 👇",
            "New song, who dis? 😎",
            f"Out now: {song.title} (your new obsession)",
            "Supporting independent artists? Stream new music today 🎧",
        ],
        "video_concepts": [
            {
                "title": "Studio Session Vibe",
                "description": "Behind-the-scenes footage of song creation and production",
                "hook": "Making magic in the studio...",
                "platform": "All platforms",
                "visual_direction": "Quick cuts of recording, mixing, and artist vibe. Use colored lighting.",
            },
            {
                "title": "Lyric Video",
                "description": "Song playing over animated or motion lyric visuals",
                "hook": "New song. New lyrics. New you.",
                "platform": "YouTube, Instagram Reels, TikTok",
                "visual_direction": "Clean typography, animated transitions, matching song mood colors.",
            },
            {
                "title": "Artist Performance",
                "description": "Artist lip-syncing or performing to the song",
                "hook": "How I felt making this song...",
                "platform": "TikTok, Instagram Reels",
                "visual_direction": "Close-ups, outfit changes, confident energy. Trending audio overlay.",
            },
            {
                "title": "Fan Reactions",
                "description": "Compile reactions from first listeners",
                "hook": "Wait till the drop 🔥",
                "platform": "Instagram Reels, TikTok, YouTube",
                "visual_direction": "Genuine reactions, text overlays, trending sounds.",
            },
            {
                "title": "Countdown Teaser",
                "description": "30-second clip of best part of song",
                "hook": "3 days until...",
                "platform": "All platforms",
                "visual_direction": "Minimal visuals, song clip overlay, big bold text countdown.",
            },
            {
                "title": "Break-down Explanation",
                "description": "Artist explains inspiration or production process",
                "hook": "Let me tell you about this song...",
                "platform": "Instagram Reels, YouTube Shorts, TikTok",
                "visual_direction": "Talking head, animated graphics showing production elements.",
            },
            {
                "title": "Challenge Starter",
                "description": "Create a fun challenge using the song",
                "hook": "Can you finish the dance?",
                "platform": "TikTok, Instagram Reels",
                "visual_direction": "Energetic, fun choreography or trend interpretation.",
            },
            {
                "title": "Release Day Hype",
                "description": "Celebration video on release day",
                "hook": "IT'S OUT NOW 🚀",
                "platform": "All platforms",
                "visual_direction": "High energy, confetti, celebration vibes.",
            },
            {
                "title": "Lyric Reaction",
                "description": "Artist reacts to listener comments about lyrics",
                "hook": "Y'all are getting the message...",
                "platform": "Instagram Reels, TikTok",
                "visual_direction": "Split screen with comments, artist reactions.",
            },
            {
                "title": "Playlist Pitch",
                "description": "Why this song deserves to be on playlists",
                "hook": "If you make playlists...",
                "platform": "YouTube, Instagram Reels",
                "visual_direction": "Professional, clean, with cover art and stats.",
            },
        ],
        "hashtags": [
            "#NewMusic",
            "#IndependentArtist",
            "#NewSong",
            f"#{song.genre_preferences[0] if song.genre_preferences else 'Music'}",
            "#OriginalMusic",
            "#UndergroundHipHop" if song.genre_preferences and "hip" in song.genre_preferences[0].lower() else "#IndieMusic",
            "#MusicProduction",
            "#ArtistLife",
            "#UpcomingArtist",
            "#MusicRelease",
            "#IndieMusic",
            "#StreamIt",
            "#MusicalArtist",
            "#SupportIndependent",
            "#NewRelease",
        ],
        "cta_examples": [
            "Stream it now on Spotify 🎧",
            "Add to your playlist 📋",
            "Tag someone who needs this",
            "What's your favorite part? 👇",
            "Follow for more new music 🔔",
            "Share with a friend who gets it",
            "Link in bio to listen everywhere",
        ],
    }


def generate_posting_schedule(
    campaign_duration_days: int,
    release_date: date | None,
    num_posts: int = 28,
) -> list[dict[str, Any]]:
    """
    Generate a deterministic posting schedule calendar.
    
    Creates a schedule with 28 days (default), rotating through content types,
    distributed across preferred platforms using music industry best posting times.
    """
    if release_date is None:
        release_date = date.today()
    
    # Calculate pre-release period (typically 2 weeks before)
    pre_release_start = release_date - timedelta(days=14)
    
    # Content types to rotate through
    content_types = [
        "teaser_clip",
        "behind_the_scenes",
        "cover_snippet",
        "fan_engagement",
        "release_countdown",
        "release_announcement",
        "remix_teaser",
    ]
    
    # Default platforms
    platforms = ["Instagram", "TikTok", "YouTube", "Spotify"]
    
    # Music industry best posting times (by hour in UTC, adjust for timezones)
    # Typically 9am, 2pm, 7pm local time
    best_posting_times = [
        "09:00",  # Morning (often 9am local)
        "14:00",  # Afternoon (often 2pm local)
        "19:00",  # Evening (often 7pm local)
    ]
    
    schedule = []
    current_date = pre_release_start
    content_type_idx = 0
    platform_idx = 0
    time_idx = 0
    
    for day_num in range(campaign_duration_days):
        # Determine if this is a posting day (post 5-7 times per week)
        day_of_week = current_date.weekday()  # 0=Monday, 6=Sunday
        
        # Post Monday-Friday and Saturday (6 days/week), skip most Sundays
        is_posting_day = day_of_week != 6  # Skip Sundays mostly
        
        if is_posting_day:
            # Determine content type and platform for this post
            content_type = content_types[content_type_idx % len(content_types)]
            platform = platforms[platform_idx % len(platforms)]
            posting_time = best_posting_times[time_idx % len(best_posting_times)]
            
            # Tailor caption based on phase
            days_until_release = (release_date - current_date).days
            if days_until_release > 7:
                phase = "pre-release"
                caption_idea = f"Getting ready for the big reveal... {content_type} teaser"
            elif days_until_release > 0:
                phase = "pre-release (final week)"
                caption_idea = f"{content_type.replace('_', ' ').title()} - {days_until_release} days to go!"
            elif days_until_release == 0:
                phase = "release"
                caption_idea = "🚀 IT'S OUT NOW! Stream everywhere 🎵"
            else:
                phase = "post-release"
                caption_idea = f"Thanks for the support! Check out {content_type.replace('_', ' ')}"
            
            schedule.append({
                "date": current_date.isoformat(),
                "day": current_date.strftime("%A"),
                "posting_time": posting_time,
                "platform": platform,
                "content_type": content_type,
                "caption_idea": caption_idea,
                "call_to_action": "Stream now" if phase == "release" else "Add to playlist / Follow",
                "required_assets": ["Song clip", "Cover art", "Text overlay"],
                "paid_promotion_status": "organic" if phase == "pre-release" else "consider paid",
                "paid_budget": 0 if phase == "pre-release" else 5,
                "phase": phase,
            })
            
            content_type_idx += 1
            platform_idx += 1
            time_idx += 1
        
        current_date += timedelta(days=1)
    
    return schedule
