#!/usr/bin/env python3
"""Нарезка мемов для канала: запускается на компьютере владельца, а не на GitHub.

Что делает за один запуск:
1. ищет на YouTube русские нарезки «мемы бравл старс»;
2. берёт данные YouTube о самых пересматриваемых моментах ролика (график над полосой прокрутки);
3. скачивает только этот фрагмент (20-45 секунд), а не весь ролик;
4. загружает его через бота в Telegram (он приходит тебе в личку, можно проверить);
5. записывает фрагмент в clips.json репозитория: бот канала сам поставит его в мемы с подписью
   и ссылкой на автора нарезки.

Настройки в config.txt рядом с этим файлом (образец: config.example.txt).
Важно: нарезки принадлежат их авторам. Публикуя фрагменты, канал берёт ответственность на себя;
если автор попросит убрать, удали пост.
"""
import base64
import json
import mimetypes
import re
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DONE = HERE / "done.json"
MAX_SIZE = 49_000_000  # Бот может загрузить в Telegram файл до 50 МБ.
BAD = re.compile(r"(18\+|порн|секс|nsfw|казино|ставк|бесплатн\w* гем|взлом|приватк|политик|путин|зеленск)",
                 re.IGNORECASE)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def load_config():
    path = HERE / "config.txt"
    if not path.exists():
        sys.exit("Нет файла config.txt. Скопируй config.example.txt в config.txt и заполни его.")
    config = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            config[key.strip()] = value.strip()
    for key in ("BOT_TOKEN", "CHANNEL", "GITHUB_TOKEN", "REPO"):
        if not config.get(key):
            sys.exit(f"В config.txt не заполнено {key}")
    return config


# ---------- YouTube (yt-dlp) ----------


def ytdlp_command():
    """yt-dlp.exe рядом с программой или в PATH (официальная сборка с GitHub), иначе модуль Python."""
    import shutil

    local = HERE / "yt-dlp.exe"
    if local.exists():
        return [str(local)]
    found = shutil.which("yt-dlp")
    return [found] if found else [sys.executable, "-m", "yt_dlp"]


LOGIN = []  # Вход в YouTube под аккаунтом владельца: --cookies-from-browser или --cookies.


def login_args(config):
    """Если YouTube просит подтвердить, что ты не бот, программа заходит под твоим аккаунтом
    из браузера (COOKIES_BROWSER) или из файла cookies.txt (COOKIES_FILE)."""
    if config.get("COOKIES_FILE"):
        path = Path(config["COOKIES_FILE"])
        return ["--cookies", str(path if path.is_absolute() else HERE / path)]
    if config.get("COOKIES_BROWSER"):
        return ["--cookies-from-browser", config["COOKIES_BROWSER"]]
    return []


def ytdlp(*args, timeout=600):
    return subprocess.run([*ytdlp_command(), *LOGIN, *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def russian(title):
    letters = re.findall(r"[^\W\d_]", title or "")
    cyrillic = [c for c in letters if "а" <= c.lower() <= "я" or c.lower() == "ё"]
    return len(cyrillic) >= 5 and len(cyrillic) / len(letters) >= 0.3


def search(query, limit=20):
    done = ytdlp("--flat-playlist", "--print", "%(id)s\t%(duration)s\t%(title)s", f"ytsearch{limit}:{query}")
    rows = []
    for line in done.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            try:
                duration = float(parts[1])
            except ValueError:
                continue
            rows.append({"id": parts[0], "duration": duration, "title": parts[2]})
    if not rows:
        # Ничего не нашлось: показываем, что ответил YouTube, чтобы было понятно почему.
        print(f"  YouTube ничего не вернул. Ответ yt-dlp: {(done.stderr or done.stdout).strip()[-400:] or 'пусто'}")
    return rows


def video_info(video_id):
    done = ytdlp("--skip-download", "-j", f"https://www.youtube.com/watch?v={video_id}", timeout=180)
    try:
        return json.loads(done.stdout)
    except ValueError:
        error = done.stderr.strip()
        if "not a bot" in error or "cookies" in error:
            hint = ("YouTube просит войти. Впиши в config.txt строку COOKIES_BROWSER=firefox "
                    "(и войди в YouTube в Firefox) или COOKIES_FILE=cookies.txt" if not LOGIN else
                    "Не удалось войти через браузер: закрой браузер и запусти снова, либо используй COOKIES_FILE")
            print(f"  {hint}")
        else:
            print(f"  YouTube не отдал данные ролика: {error[-200:]}")
        return None


def peaks(heatmap, duration, count=1, shortest=20, longest=45):
    """Самые пересматриваемые фрагменты: [(начало, конец)] в секундах.

    heatmap: [{"start_time", "end_time", "value"}] от YouTube. Заставку в начале и
    концовку не берём, фрагменты не пересекаются (между ними минимум минута)."""
    if not heatmap:
        return []
    usable = [h for h in heatmap if h["start_time"] >= max(10, duration * 0.05)
              and h["end_time"] <= duration * 0.97]
    chosen = []
    for top in sorted(usable, key=lambda h: -h["value"]):
        if len(chosen) >= count:
            break
        if any(abs(top["start_time"] - start) < 60 for start, _ in chosen):
            continue
        # Расширяем пик на соседние отрезки, которые смотрят почти так же часто.
        start, end = top["start_time"], top["end_time"]
        for h in sorted(usable, key=lambda h: h["start_time"]):
            if h["value"] >= top["value"] * 0.7:
                if h["end_time"] >= start - 1 and h["start_time"] < start:
                    start = h["start_time"]
        for h in sorted(usable, key=lambda h: h["start_time"]):
            if h["value"] >= top["value"] * 0.7 and h["start_time"] <= end + 1 and h["end_time"] > end:
                end = h["end_time"]
        middle = (start + end) / 2
        length = min(max(end - start + 6, shortest), longest)
        start = max(0, middle - length / 2)
        end = min(duration, start + length)
        chosen.append((int(start), int(end)))
    return chosen


def download(video_id, start, end, folder):
    out = Path(folder) / f"{video_id}-{start}.mp4"
    done = ytdlp("-f", "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4]/b[height<=720]",
                 "--download-sections", f"*{start}-{end}", "--force-keyframes-at-cuts",
                 "--merge-output-format", "mp4", "-o", str(out), f"https://www.youtube.com/watch?v={video_id}")
    if not out.exists():
        print(f"  Не скачалось: {done.stderr.strip()[-300:]}")
        return None
    if out.stat().st_size > MAX_SIZE:
        print("  Фрагмент больше 50 МБ, пропускаю")
        return None
    return out


# ---------- Telegram ----------


def telegram(token, method, fields=None, file_field=None, path=None):
    url = f"https://api.telegram.org/bot{token}/{method}"
    if path is None:
        request = urllib.request.Request(url, data=json.dumps(fields or {}).encode(),
                                         headers={"Content-Type": "application/json"})
    else:
        boundary = secrets.token_hex(16)
        body = bytearray()
        for name, value in (fields or {}).items():
            body += f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        kind = mimetypes.guess_type(path.name)[0] or "video/mp4"
        body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{path.name}"\r\n'
                 f"Content-Type: {kind}\r\n\r\n").encode()
        body += path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        request = urllib.request.Request(url, data=bytes(body),
                                         headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return json.load(response)["result"]
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Telegram {error.code}: {error.read().decode('utf-8', 'replace')[:200]}") from None


def owner_id(config):
    if config.get("OWNER_ID"):
        return int(config["OWNER_ID"])
    members = telegram(config["BOT_TOKEN"], "getChatAdministrators", {"chat_id": config["CHANNEL"]})
    return next(m["user"]["id"] for m in members if m["status"] == "creator")


# ---------- GitHub (clips.json) ----------


def github(config, method, body=None):
    url = f"https://api.github.com/repos/{config['REPO']}/contents/clips.json"
    request = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None,
                                     headers={"Authorization": f"Bearer {config['GITHUB_TOKEN']}",
                                              "Accept": "application/vnd.github+json",
                                              "User-Agent": "brawl-clipper"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def save_clip(config, clip):
    """Дописывает фрагмент в clips.json репозитория (повторяет, если файл успели поменять)."""
    for _ in range(5):
        try:
            current = github(config, "GET")
            clips, sha = json.loads(base64.b64decode(current["content"]).decode("utf-8")), current["sha"]
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            clips, sha = [], None
        clips = (clips + [clip])[-100:]
        body = {"message": f"Новый фрагмент-мем {clip['id']}",
                "content": base64.b64encode(json.dumps(clips, ensure_ascii=False, indent=1).encode()).decode()}
        if sha:
            body["sha"] = sha
        try:
            github(config, "PUT", body)
            return
        except urllib.error.HTTPError as error:
            if error.code not in (409, 422):
                raise
            time.sleep(3)
    raise RuntimeError("не удалось записать clips.json в GitHub")


# ---------- Главное ----------


def main():
    config = load_config()
    LOGIN[:] = login_args(config)
    if LOGIN:
        print("Вход в YouTube: " + ("файл cookies" if "--cookies" in LOGIN else f"браузер {LOGIN[1]}"))
    done = set(json.loads(DONE.read_text(encoding="utf-8"))) if DONE.exists() else set()
    want = int(config.get("CLIPS_PER_RUN", "2"))
    queries = [q.strip() for q in config.get("QUERIES", "мемы бравл старс;смешные моменты бравл старс").split(";")]
    owner = owner_id(config)
    made = 0
    with tempfile.TemporaryDirectory() as folder:
        for query in queries:
            if made >= want:
                break
            print(f"Ищу: {query}")
            found = search(query)
            fresh = [v for v in found if v["id"] not in done and 120 <= v["duration"] <= 1800
                     and russian(v["title"]) and not BAD.search(v["title"])]
            print(f"  Найдено роликов: {len(found)}, подходят (русские, 2-30 минут, новые): {len(fresh)}")
            for video in fresh:
                if made >= want:
                    break
                done.add(video["id"])
                print(f"- {video['title']}")
                info = video_info(video["id"])
                if not info:
                    continue
                spans = peaks(info.get("heatmap"), video["duration"])
                if not spans:
                    print("  У ролика нет данных о пересматриваемых моментах, пропускаю")
                    continue
                for start, end in spans:
                    print(f"  Пик просмотров: {start // 60}:{start % 60:02d}-{end // 60}:{end % 60:02d}, скачиваю")
                    path = download(video["id"], start, end, folder)
                    if not path:
                        continue
                    channel = info.get("channel") or info.get("uploader") or "YouTube"
                    caption = (f"Новый фрагмент для канала: {video['title']} ({channel}). "
                               "Бот поставит его в мемы сам. Если не нравится, удали его в «🤖 Автопосты».")
                    sent = telegram(config["BOT_TOKEN"], "sendVideo",
                                    {"chat_id": owner, "caption": caption[:1000], "supports_streaming": "true",
                                     "disable_notification": "true"}, "video", path)
                    clip = {"id": f"{video['id']}-{start}", "file_id": sent["video"]["file_id"],
                            "url": f"https://www.youtube.com/watch?v={video['id']}&t={start}s",
                            "channel": channel, "channel_url": info.get("channel_url") or "",
                            "caption": f"Самый пересматриваемый момент из «{video['title'][:90]}»",
                            "added": int(time.time())}
                    save_clip(config, clip)
                    made += 1
                    print("  Готово: отправлено боту и добавлено в мемы")
    DONE.write_text(json.dumps(sorted(done), ensure_ascii=False), encoding="utf-8")
    print(f"Новых фрагментов: {made}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 - понятное сообщение вместо длинной ошибки
        print(f"Ошибка: {type(error).__name__}: {error}")
        sys.exit(1)
