"""Выбор самых пересматриваемых фрагментов в программе нарезки."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("clipper", Path(__file__).resolve().parent.parent / "local" / "clipper.py")
clipper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clipper)


def heat(values, step=6):
    return [{"start_time": i * step, "end_time": (i + 1) * step, "value": v} for i, v in enumerate(values)]


def test_peak_skips_intro_and_has_sane_length():
    values = [1.0, 0.9] + [0.1] * 40 + [0.5, 0.95, 0.9, 0.4] + [0.1] * 54  # 600 секунд
    spans = clipper.peaks(heat(values), 600)
    assert len(spans) == 1
    start, end = spans[0]
    assert 240 <= start <= 270 and 20 <= end - start <= 45  # Пик на 258-270 с, заставка в начале не взята.


def test_two_peaks_do_not_overlap():
    values = [0.1] * 20 + [0.9] + [0.1] * 30 + [0.8] + [0.1] * 48
    spans = clipper.peaks(heat(values), 600, count=2)
    assert len(spans) == 2 and abs(spans[0][0] - spans[1][0]) >= 60


def test_no_heatmap():
    assert clipper.peaks(None, 600) == [] and clipper.peaks([], 600) == []


def test_russian_titles():
    assert clipper.russian("Смешные моменты бравл старс #5")
    assert not clipper.russian("Brawl Stars memes compilation")
