#!/usr/bin/env python3
"""Нарезка смешных моментов из видео, которое владелец прислал боту.

python3 clipbot.py FILE_ID КОЛИЧЕСТВО CHAT_ID

Запускается отдельным workflow clip.yml (его запускает админ-бот), чтобы бот не замолкал на время
нарезки. Gemini смотрит видео и выбирает моменты, ffmpeg их вырезает, бот присылает владельцу
пронумерованные ролики, а их список сохраняется в clip_batch.json. Владелец отвечает «добавь 1 3»
или жмёт кнопки, и выбранные ролики уходят в очередь.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import bot

BATCH = bot.ROOT / "clip_batch.json"
GEMINI = "https://generativelanguage.googleapis.com"
MODELS = ["gemini-flash-latest", "gemini-3.8-flash", "gemini-flash-lite-latest"]
PROMPT = """Это видео по игре Brawl Stars. Найди {count} самых смешных и ярких моментов: забавные
ситуации в матче, фейлы, неожиданные повороты, удачные трюки. Каждый момент длиной 5-45 секунд,
моменты не пересекаются. Время в секундах от начала видео (длина видео {duration} секунд).
Без моментов с оскорблениями, политикой, 18+ и личными данными.
Ответь только JSON-массивом от самого смешного к менее смешному:
[{{"start": секунда начала, "end": секунда конца, "title": "смешная подпись по-русски до 80 символов"}}]"""


def tg(method, **payload):
    return bot.call(os.environ["TELEGRAM_BOT_TOKEN"], method, payload).get("result")


def download(file_id, folder):
    info = tg("getFile", file_id=file_id)
    if not info or not info.get("file_path"):
        raise RuntimeError("Telegram не отдал файл. Бот может скачать видео только до 20 МБ.")
    url = f"https://api.telegram.org/file/bot{os.environ['TELEGRAM_BOT_TOKEN']}/{info['file_path']}"
    path = Path(folder) / "source.mp4"
    with urllib.request.urlopen(url, timeout=300) as response:
        path.write_bytes(response.read())
    return path


def duration(path):
    done = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                          capture_output=True, text=True)
    return float(done.stdout.strip() or 0)


def gemini_upload(path):
    """Загружает видео в Gemini Files API и ждёт, пока оно обработается."""
    key = os.environ["GEMINI_API_KEY"]
    data = path.read_bytes()
    start = urllib.request.Request(
        f"{GEMINI}/upload/v1beta/files", data=json.dumps({"file": {"display_name": "brawl"}}).encode(),
        headers={"x-goog-api-key": key, "X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start",
                 "X-Goog-Upload-Header-Content-Length": str(len(data)),
                 "X-Goog-Upload-Header-Content-Type": "video/mp4", "Content-Type": "application/json"})
    with urllib.request.urlopen(start, timeout=60) as response:
        upload_url = response.headers["X-Goog-Upload-URL"]
    upload = urllib.request.Request(upload_url, data=data, headers={
        "Content-Length": str(len(data)), "X-Goog-Upload-Offset": "0",
        "X-Goog-Upload-Command": "upload, finalize"})
    with urllib.request.urlopen(upload, timeout=600) as response:
        file = json.load(response)["file"]
    for _ in range(60):
        if file.get("state") == "ACTIVE":
            return file["uri"]
        if file.get("state") == "FAILED":
            raise RuntimeError("Gemini не смог обработать видео")
        time.sleep(5)
        request = urllib.request.Request(f"{GEMINI}/v1beta/{file['name']}", headers={"x-goog-api-key": key})
        with urllib.request.urlopen(request, timeout=60) as response:
            file = json.load(response)
    raise RuntimeError("Gemini слишком долго обрабатывал видео")


def gemini_moments(uri, count, length):
    key = os.environ["GEMINI_API_KEY"]
    body = json.dumps({"contents": [{"role": "user", "parts": [
        {"file_data": {"mime_type": "video/mp4", "file_uri": uri}},
        {"text": PROMPT.format(count=count, duration=int(length))}]}],
        "generationConfig": {"temperature": 0.4}}).encode()
    last = None
    for model in MODELS:
        request = urllib.request.Request(f"{GEMINI}/v1beta/models/{model}:generateContent", data=body,
                                         headers={"Content-Type": "application/json", "x-goog-api-key": key})
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                reply = json.load(response)
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last = error.read().decode("utf-8", "replace")[:200] if hasattr(error, "read") else error
            print(f"Gemini {model}: {last}")
            continue
        text = "".join(p.get("text", "") for p in (reply.get("candidates") or [{}])[0]
                       .get("content", {}).get("parts", []))
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            print(f"Ответил {model}")
            return json.loads(match.group(0))
    raise RuntimeError(f"Gemini не ответил: {last}")


def clean_moments(raw, count, length):
    """Только моменты внутри видео, нормальной длины и без пересечений."""
    chosen = []
    for item in raw:
        try:
            start, end = float(item["start"]), float(item["end"])
        except (KeyError, TypeError, ValueError):
            continue
        start, end = max(0.0, start), min(length, end)
        if end - start < 3:
            continue
        if end - start > 60:
            end = start + 60
        if any(start < e and end > s for s, e, _ in chosen):
            continue
        chosen.append((start, end, str(item.get("title") or "Смешной момент")[:80]))
        if len(chosen) >= count:
            break
    return chosen


def cut(source, start, end, out):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-to", f"{end:.2f}",
                    "-i", str(source), "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-c:a", "aac", "-movflags", "+faststart", str(out)], check=True, timeout=600)
    return out


def stamp(seconds):
    return f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


def main():
    file_id, count, chat = sys.argv[1], max(1, min(int(sys.argv[2]), 10)), int(sys.argv[3])
    batch = f"{int(time.time())}"
    try:
        with tempfile.TemporaryDirectory() as folder:
            source = download(file_id, folder)
            length = duration(source)
            print(f"Видео {length:.0f} с, ищу {count} моментов")
            moments = clean_moments(gemini_moments(gemini_upload(source), count, length), count, length)
            if not moments:
                tg("sendMessage", chat_id=chat, text="Gemini не нашёл подходящих моментов в этом видео 🤷")
                return
            clips = []
            for number, (start, end, title) in enumerate(moments, 1):
                path = cut(source, start, end, Path(folder) / f"clip{number}.mp4")
                fields = {"chat_id": chat, "caption": f"Момент {number}: {title} ({stamp(start)}–{stamp(end)})",
                          "supports_streaming": "true", "reply_markup": json.dumps({"inline_keyboard": [[
                              {"text": f"➕ {number} в очередь", "callback_data": f"ca:{batch}:{number}"},
                              {"text": "⏭ Следующим", "callback_data": f"cn:{batch}:{number}"},
                              {"text": "🚀 Сейчас", "callback_data": f"cp:{batch}:{number}"}]]})}
                sent = bot.send_file(os.environ["TELEGRAM_BOT_TOKEN"], "sendVideo", fields, "video", path)
                clips.append({"n": number, "file_id": sent["result"]["video"]["file_id"], "title": title})
            bot.write_json(BATCH, {"batch": batch, "clips": clips})
            tg("sendMessage", chat_id=chat, text=(
                f"Готово: {len(clips)} нарезок. Напиши, какие добавить в очередь, например «добавь 1 3» "
                "или «добавь все». «следующим 2» поставит ролик первым в очереди. Можно и кнопками под роликами."))
    except Exception as error:  # noqa: BLE001 - владелец должен узнать, что не получилось
        tg("sendMessage", chat_id=chat, text=f"Нарезка не получилась: {error}")
        raise


if __name__ == "__main__":
    main()
