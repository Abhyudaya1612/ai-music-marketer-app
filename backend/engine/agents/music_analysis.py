"""Music Analysis Agent 🎵 — audio, lyrics, structure, BPM, key, energy, hooks."""
from __future__ import annotations
from collections import Counter
from ..base import BaseAgent
from ..schemas import SongInput, SongIntelligence


class MusicAnalysisAgent(BaseAgent):
    name = "MUSIC_ANALYSIS_AGENT"
    emoji = "🎵"

    GENRE_PROFILES = {
        "pop":        dict(bpm=118, energy=0.72, valence=0.68, mood="upbeat, radio-ready"),
        "indie":      dict(bpm=104, energy=0.55, valence=0.52, mood="authentic, textured"),
        "electronic": dict(bpm=124, energy=0.82, valence=0.60, mood="driving, atmospheric"),
        "hip-hop":    dict(bpm=90,  energy=0.66, valence=0.50, mood="confident, rhythmic"),
        "rock":       dict(bpm=132, energy=0.80, valence=0.58, mood="anthemic, raw"),
        "r&b":        dict(bpm=95,  energy=0.50, valence=0.62, mood="smooth, emotive"),
        "lo-fi":      dict(bpm=78,  energy=0.32, valence=0.48, mood="mellow, introspective"),
    }
    KEYS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    THEME_LEXICON = {
        "love & relationships": ["love", "heart", "you and i", "kiss", "hold me"],
        "nightlife & escape":   ["night", "neon", "city", "drive", "lights", "skyline"],
        "ambition & success":   ["grind", "win", "money", "crown", "top", "empire"],
        "loss & longing":       ["gone", "miss", "empty", "ghost", "fade", "without you"],
        "self-discovery":       ["find", "who i am", "mirror", "change", "become"],
    }

    def run(self, song: SongInput) -> SongIntelligence:
        self.log(f"Analyzing '{song.title}' by {song.artist} ...")
        profile = self._match_genre(song.genre)
        bpm = song.bpm or profile["bpm"]
        key = song.musical_key or self._derive_key(song.title)
        energy = song.energy or profile["energy"]
        valence = song.valence or profile["valence"]

        intel = SongIntelligence(
            bpm=bpm, musical_key=key, energy=round(energy, 2),
            valence=round(valence, 2), mood=profile["mood"],
            structure=self._infer_structure(energy),
            hooks=self._extract_hooks(song.lyrics),
            lyrical_themes=self._extract_themes(song.lyrics),
            production_notes=[
                f"Mid-side width boost on chorus for {key} lift",
                "Keep intro under 8s — short attention window",
                "Feature hook within first 15 seconds for short-form clips",
            ],
            a_r_insights=self._aandr_notes(bpm, energy, valence,
                                           self._extract_themes(song.lyrics)),
        )
        self.log(f"SongIntelligence ready: {bpm} BPM, key of {key}, "
                 f"energy {intel.energy:.2f}, {len(intel.hooks)} hook(s)")
        return intel

    def _match_genre(self, genre: str) -> dict:
        g = genre.lower()
        for tag, profile in self.GENRE_PROFILES.items():
            if tag in g:
                return profile
        return dict(bpm=110, energy=0.6, valence=0.55, mood="versatile, mid-energy")

    def _derive_key(self, seed: str) -> str:
        return self.KEYS[sum(ord(c) for c in seed) % len(self.KEYS)]

    def _infer_structure(self, energy: float) -> list[str]:
        if energy > 0.7:
            return ["intro", "verse", "pre-chorus", "chorus",
                    "verse", "chorus", "bridge", "final chorus"]
        return ["intro", "verse", "chorus", "verse", "chorus", "outro"]

    def _extract_themes(self, lyrics: str) -> list[str]:
        text = lyrics.lower()
        found = [t for t, words in self.THEME_LEXICON.items()
                 if any(w in text for w in words)]
        return found or ["general storytelling"]

    def _extract_hooks(self, lyrics: str) -> list[str]:
        lines = [l.strip() for l in lyrics.splitlines() if l.strip()]
        if not lines:
            return ["Instrumental drop at chorus entry"]
        counts = Counter(lines)
        repeated = [l for l, c in counts.items() if c > 1]
        if repeated:
            return sorted(repeated, key=len, reverse=True)[:2]
        return [max(lines, key=lambda l: len(l.split()))]

    def _aandr_notes(self, bpm, energy, valence, themes) -> list[str]:
        notes = []
        if bpm >= 120: notes.append("Playlist fit: high-energy editorial & workout lists")
        elif bpm <= 85: notes.append("Playlist fit: chill/late-night editorial lists")
        else: notes.append("Playlist fit: indie/pop crossover lists")
        if valence < 0.5: notes.append("Emotional contrast angle: pitch as cathartic anthem")
        if "nightlife & escape" in themes:
            notes.append("Sync potential: nightlife / automotive / fashion briefs")
        return notes or ["Solid commercial structure — prioritize playlist pitching"]
