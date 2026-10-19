import os
import pytest
from datetime import datetime
from main import (
    extract_radio_slug,
    assemble_time,
    format_track_info,
    detect_language,
    get_app_paths,
    parse_args
)


class TestExtractRadioSlug:
    def test_full_url_with_trailing_slash(self):
        url = "https://www.socialradio.com.br/radio/verdeolivaresende/"
        assert extract_radio_slug(url) == "verdeolivaresende"

    def test_full_url_without_trailing_slash(self):
        url = "https://www.socialradio.com.br/radio/verdeolivaresende"
        assert extract_radio_slug(url) == "verdeolivaresende"

    def test_another_station_url(self):
        url = "https://socialradio.com.br/radio/rock-fm/"
        assert extract_radio_slug(url) == "rock-fm"

    def test_plain_slug(self):
        assert extract_radio_slug("verdeolivaresende") == "verdeolivaresende"

    def test_plain_slug_with_slash_and_spaces(self):
        assert extract_radio_slug("  verdeolivaresende/  ") == "verdeolivaresende"


class TestAssembleTime:
    def test_midnight(self):
        dt = datetime(2026, 10, 19, 0, 0)
        assert assemble_time(dt) == "meia noite"

    def test_noon(self):
        dt = datetime(2026, 10, 19, 12, 0)
        assert assemble_time(dt) == "meio dia"

    def test_one_o_clock(self):
        dt = datetime(2026, 10, 19, 1, 0)
        assert assemble_time(dt) == "uma em ponto"

    def test_two_thirty(self):
        dt = datetime(2026, 10, 19, 14, 30)
        assert assemble_time(dt) == "duas e meia"

    def test_standard_time(self):
        dt = datetime(2026, 10, 19, 15, 45)
        assert assemble_time(dt) == "3 e 45"


class TestFormatTrackInfo:
    def test_artist_and_title(self):
        meta = {"title": "BILLIE JEAN", "artist": "MICHAEL JACKSON", "is_commercial": False}
        assert format_track_info(meta, "Verde Oliva") == "Michael Jackson - Billie Jean"

    def test_title_only(self):
        meta = {"title": "BILLIE JEAN", "artist": None, "is_commercial": False}
        assert format_track_info(meta, "Verde Oliva") == "Billie Jean"

    def test_commercial_break(self):
        meta = {"title": "COMMERCIAL", "artist": "SPONSOR", "is_commercial": True}
        assert format_track_info(meta, "Verde Oliva") == "Verde Oliva"

    def test_none_metadata(self):
        assert format_track_info(None, "Verde Oliva") == "Verde Oliva"

    def test_corrupted_unicode_replacement(self):
        meta = {"title": "BAD \ufffd TITLE", "artist": "ARTIST", "is_commercial": False}
        assert format_track_info(meta, "Verde Oliva") == "Verde Oliva"


class TestDetectLanguage:
    def test_detect_english(self):
        name, code = detect_language("Michael Jackson - Billie Jean")
        assert code == "en"
        assert name == "English"

    def test_detect_portuguese(self):
        name, code = detect_language("Legião Urbana - Pais E Filhos")
        assert code == "pt"
        assert name == "Portuguese"

    def test_speak_hu3br_override(self):
        name, code = detect_language("Michael Jackson - Billie Jean", speak_hu3br=True)
        assert code == "pt"
        assert name == "Português"


class TestAppPaths:
    def test_get_app_paths_creation(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        art_path, log_path = get_app_paths()
        assert art_path.endswith("temp_art.png")
        assert log_path.endswith("oliva_log.txt")
        assert os.path.exists(os.path.dirname(art_path))
        assert os.path.exists(os.path.dirname(log_path))


class TestParseArgs:
    def test_parse_args_defaults(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["main.py"])
        args = parse_args()
        assert args.watch is False
        assert args.interval == 15
        assert args.dry_run is False

    def test_parse_args_custom(self, monkeypatch):
        monkeypatch.setattr("sys.argv", [
            "main.py", "--watch", "-i", "30", "--radio", "minha-radio", "--dry-run"
        ])
        args = parse_args()
        assert args.watch is True
        assert args.interval == 30
        assert args.radio == "minha-radio"
        assert args.dry_run is True
