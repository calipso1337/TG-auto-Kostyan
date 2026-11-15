"""Проверки подбора официальных фонов."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import art


def test_letterboxed_shorts_frame(tmp_path):
    shorts = Image.new("RGB", (1280, 720), (0, 0, 0))
    ImageDraw.Draw(shorts).rectangle((440, 0, 840, 720), fill=(200, 120, 40))
    shorts.save(tmp_path / "s.jpg")
    full = Image.new("RGB", (1280, 720), (60, 140, 230))
    full.save(tmp_path / "f.jpg")
    assert art.letterboxed(tmp_path / "s.jpg") and not art.letterboxed(tmp_path / "f.jpg")


def test_pick_prefers_topic_then_rotates():
    index = [{"id": "a", "title": "Frogs Brawl Talk", "path": "a"},
             {"id": "b", "title": "Ranked season", "path": "b"},
             {"id": "c", "title": "Hypercharge", "path": "c"}]
    used = []
    assert art.pick("Громожабы и frogs", index, used)["path"] == "a"
    picks = {art.pick("что-то другое", index, used)["path"] for _ in range(2)}
    assert picks == {"b", "c"}
    assert art.pick("", [], used) is None


def test_pick_mixes_screenshots_and_art():
    index = [{"id": f"gp-{n}", "title": "", "path": f"s{n}"} for n in range(20)]
    index += [{"id": f"yt-{n}", "title": "", "path": f"a{n}"} for n in range(20)]
    used = []
    kinds = [art.pick("", index, used)["id"][:2] for _ in range(40)]
    assert 8 <= kinds.count("gp") <= 32


def test_frames_never_repeat():
    index = [{"id": f"yt-v{v}-{n}", "video": f"v{v}", "title": "", "path": f"v{v}-{n}"}
             for v in range(3) for n in (1, 2, 3)]
    used = []
    picked = [art.pick("", index, used)["id"] for _ in range(9)]
    assert len(set(picked)) == 9  # Все кадры разные.
    assert art.pick("", index, used) is None  # Кадры кончились: лучше градиент, чем повтор.
    assert all(art.video_of(a) != art.video_of(b) for a, b in zip(picked, picked[1:3]))


def test_album_videos_are_not_used_on_covers():
    index = [{"id": "yt-album-1", "video": "album", "title": "", "path": "a"},
             {"id": "yt-free-1", "video": "free", "title": "", "path": "f"}]
    assert art.pick("", index, [], banned_videos={"album"})["path"] == "f"
