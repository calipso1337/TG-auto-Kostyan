"""Отбор моментов из ответа Gemini."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import clipbot  # noqa: E402


def test_clean_moments():
    raw = [{"start": 10, "end": 30, "title": "Фейл"},
           {"start": 20, "end": 40, "title": "пересекается"},
           {"start": 100, "end": 300, "title": "длинный"},
           {"start": 590, "end": 700, "title": "за концом"},
           {"start": "x"}, {"start": 50, "end": 51}]
    moments = clipbot.clean_moments(raw, 5, 600)
    assert moments == [(10.0, 30.0, "Фейл"), (100.0, 160.0, "длинный"), (590.0, 600.0, "за концом")]
    assert len(clipbot.clean_moments(raw, 1, 600)) == 1
    assert clipbot.stamp(95) == "1:35"
