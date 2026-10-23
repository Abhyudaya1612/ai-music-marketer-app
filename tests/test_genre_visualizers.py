"""Tests for genre-based visualizer theming."""
from __future__ import annotations

import pytest

from backend.services.genre_visualizer import (
    GenreThemeConfig,
    GenreVisualizerError,
    detect_genre_from_metadata,
    get_all_genres,
    get_ffmpeg_filters,
    get_genre_with_config,
    load_genre_theme,
    validate_theme_contrast,
)


class TestGenreThemeLoading:
    """Test loading genre themes."""

    def test_load_electronic_genre(self):
        theme = load_genre_theme("electronic")
        assert theme.genre == "electronic"
        assert theme.visualizer_type == "spectrum"
        assert "#00FF00" in theme.colors
        assert theme.lyrics_font_size > 0

    def test_load_hip_hop_genre(self):
        theme = load_genre_theme("hip-hop")
        assert theme.genre == "hip-hop"
        assert theme.lyrics_position == "center"

    def test_load_rock_genre(self):
        theme = load_genre_theme("rock")
        assert theme.genre == "rock"
        assert theme.visualizer_type in ("waveform", "spectrum")

    def test_load_all_genres(self):
        genres = get_all_genres()
        assert len(genres) >= 50
        assert "electronic" in genres
        assert "hip-hop" in genres
        assert "rock" in genres
        assert "pop" in genres
        assert "jazz" in genres
        assert "classical" in genres
        assert "ambient" in genres
        assert "lo-fi" in genres
        assert "k-pop" in genres
        assert "j-pop" in genres

    def test_invalid_genre_fallback(self):
        theme = load_genre_theme("unknown-invalid-genre")
        assert theme.genre == "electronic"

    def test_none_genre_defaults_to_electronic(self):
        theme = load_genre_theme(None)
        assert theme.genre == "electronic"

    def test_empty_string_defaults_to_electronic(self):
        theme = load_genre_theme("")
        assert theme.genre == "electronic"

    def test_theme_config_to_dict(self):
        theme = load_genre_theme("jazz")
        config_dict = theme.to_dict()
        assert config_dict["genre"] == "jazz"
        assert "visualizer_type" in config_dict
        assert "colors" in config_dict
        assert "lyrics_position" in config_dict
        assert "lyrics_font_size" in config_dict


class TestGenreThemeConfig:
    """Test GenreThemeConfig model."""

    def test_create_config(self):
        config = GenreThemeConfig(
            genre="test",
            visualizer_type="spectrum",
            colors=["#FF0000", "#00FF00"],
            lyrics_position="bottom",
            lyrics_font_family="Arial",
            lyrics_font_size=36,
            tempo_sync=True,
            background_color="#000000",
        )
        assert config.genre == "test"
        assert config.visualizer_type == "spectrum"
        assert len(config.colors) == 2

    def test_config_to_dict(self):
        config = GenreThemeConfig(
            genre="test",
            visualizer_type="waveform",
            colors=["#FFFFFF"],
            lyrics_position="center",
            lyrics_font_family="Georgia",
            lyrics_font_size=40,
            tempo_sync=False,
            background_color="#1a1a1a",
        )
        result = config.to_dict()
        assert result["genre"] == "test"
        assert result["lyrics_font_size"] == 40


class TestFFmpegFilters:
    """Test FFmpeg filter generation."""

    def test_spectrum_filter_generation(self):
        theme = load_genre_theme("electronic")
        filter_str = get_ffmpeg_filters(theme, 10.0)
        assert "showspectrum" in filter_str or "showwaves" in filter_str
        assert "1280x720" in filter_str
        assert "30" in filter_str

    def test_waveform_filter_generation(self):
        theme = load_genre_theme("ambient")
        filter_str = get_ffmpeg_filters(theme, 30.0)
        assert "showwaves" in filter_str or "showspectrum" in filter_str
        assert "1280x720" in filter_str

    def test_filter_contains_color_info(self):
        theme = load_genre_theme("hip-hop")
        filter_str = get_ffmpeg_filters(theme, 5.0)
        assert "0x" in filter_str or "color" in filter_str.lower()

    def test_filter_generation_various_genres(self):
        test_genres = ["rock", "pop", "jazz", "trap", "ambient", "classical"]
        for genre in test_genres:
            theme = load_genre_theme(genre)
            filter_str = get_ffmpeg_filters(theme, 3.0)
            assert isinstance(filter_str, str)
            assert len(filter_str) > 0


class TestGenreDetection:
    """Test genre auto-detection from metadata."""

    def test_detect_from_user_preferences(self):
        metadata = {}
        genre = detect_genre_from_metadata(
            metadata,
            genre_preferences=["hip-hop", "rap"],
        )
        assert genre == "hip-hop"

    def test_detect_from_empty_preferences(self):
        metadata = {}
        genre = detect_genre_from_metadata(
            metadata,
            genre_preferences=[],
        )
        assert genre == "electronic"

    def test_detect_from_no_preferences(self):
        metadata = {}
        genre = detect_genre_from_metadata(metadata)
        assert genre == "electronic"

    def test_detect_acoustic_from_features(self):
        metadata = {
            "audio_features": {
                "acousticness": {"value": 0.85, "status": "measured"}
            }
        }
        genre = detect_genre_from_metadata(metadata)
        assert genre == "acoustic"

    def test_detect_electronic_from_danceability(self):
        metadata = {
            "audio_features": {
                "danceability": {"value": 0.8, "status": "measured"},
                "acousticness": {"value": 0.2, "status": "measured"},
            }
        }
        genre = detect_genre_from_metadata(metadata)
        assert genre == "electronic"

    def test_detect_metal_from_energy(self):
        metadata = {
            "audio_features": {
                "energy": {"value": 0.9, "status": "measured"},
                "acousticness": {"value": 0.1, "status": "measured"},
            }
        }
        genre = detect_genre_from_metadata(metadata)
        assert genre == "metal"

    def test_detect_ambient_from_low_energy(self):
        metadata = {
            "audio_features": {
                "energy": {"value": 0.2, "status": "measured"}
            }
        }
        genre = detect_genre_from_metadata(metadata)
        assert genre == "ambient"


class TestThemeContrast:
    """Test contrast validation."""

    def test_white_on_black_sufficient(self):
        result = validate_theme_contrast("#FFFFFF", "#000000")
        assert result is True

    def test_black_on_white_sufficient(self):
        result = validate_theme_contrast("#000000", "#FFFFFF")
        assert result is True

    def test_white_on_white_insufficient(self):
        result = validate_theme_contrast("#FFFFFF", "#FFFFFF")
        assert result is False

    def test_red_on_black_sufficient(self):
        result = validate_theme_contrast("#FF0000", "#000000")
        assert result is True

    def test_yellow_on_white_insufficient(self):
        result = validate_theme_contrast("#FFFF00", "#FFFFFF")
        assert result is False

    def test_blue_on_black_sufficient(self):
        result = validate_theme_contrast("#0000FF", "#000000")
        assert result is True


class TestGetGenreWithConfig:
    """Test retrieving full genre configuration."""

    def test_get_genre_config_electronic(self):
        config = get_genre_with_config("electronic")
        assert config["genre"] == "electronic"
        assert "visualizer_type" in config
        assert "colors" in config
        assert "lyrics_position" in config

    def test_get_all_genres_config(self):
        genres = get_all_genres()
        for genre in genres[:5]:  # Test first 5 to avoid long test time
            config = get_genre_with_config(genre)
            assert config["genre"] == genre

    def test_fallback_to_electronic_for_unknown(self):
        config = get_genre_with_config("unknown_genre_xyz")
        assert config["genre"] == "electronic"


class TestGenreThemeProperties:
    """Test various genre theme properties."""

    def test_visualizer_types_are_valid(self):
        valid_types = ("waveform", "spectrum")
        genres = get_all_genres()
        for genre in genres:
            theme = load_genre_theme(genre)
            assert theme.visualizer_type in valid_types

    def test_lyrics_positions_are_valid(self):
        valid_positions = ("top", "bottom", "center", "flowing")
        genres = get_all_genres()
        for genre in genres:
            theme = load_genre_theme(genre)
            assert theme.lyrics_position in valid_positions

    def test_font_sizes_in_reasonable_range(self):
        genres = get_all_genres()
        for genre in genres:
            theme = load_genre_theme(genre)
            assert 20 <= theme.lyrics_font_size <= 96

    def test_colors_are_hex_format(self):
        genres = get_all_genres()
        for genre in genres[:10]:  # Sample
            theme = load_genre_theme(genre)
            for color in theme.colors:
                assert color.startswith("#")
                assert len(color) == 7  # #RRGGBB
