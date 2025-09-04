#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Bot: Download Instagram/YouTube video + caption after 10 seconds.

⚠️ فقط برای محتوایی استفاده کنید که مجاز به دانلود آن هستید.
"""

import asyncio
import os
import re
import tempfile
from pathlib import Path

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from yt_dlp import YoutubeDL

# ---- تنظیمات ----
DELAY_SECONDS = 10
TELEGRAM_MAX_BYTES = 2 * 1024 * 1024 * 1024  # ~2GB

YTDLP_OPTS_BASE = {
    "noprogress": True,
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "format": "best[ext=mp4]/bestvideo*+bestaudio/best",
}

YOUTUBE_RE = re.compile(r"^(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/).+", re.I)
INSTAGRAM_RE = re.compile(r"^(https?://)?(www\.)?instagram\.com/.+", re.I)


def is_supported_url(text: str) -> bool:
    return bool(YOUTUBE_RE.match(text) or INSTAGRAM_RE.match(text))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = (
        "سلام 👋\n"
        f"لینک اینستاگرام یا یوتیوب بفرست. بعد از {DELAY_SECONDS} ثانیه ویدیو + کپشن میاد."
    )
    await update.message.reply_text(msg)


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    url = update.message.text.strip()
    if not is_supported_url(url):
        await update.message.reply_text("فقط لینک‌های یوتیوب و اینستاگرام رو قبول می‌کنم.")
        return

    await update.message.reply_text(f"اوکی! {DELAY_SECONDS} ثانیه صبر کن …")
    await asyncio.sleep(DELAY_SECONDS)

    with tempfile.TemporaryDirectory(prefix="dlbot_") as tmpdir:
        tmp = Path(tmpdir)
        ytdlp_opts = {**YTDLP_OPTS_BASE, "outtmpl": str(tmp / "%(title)s.%(ext)s")}

        try:
            await update.message.chat.send_action(ChatAction.TYPING)
            info = await asyncio.to_thread(_download_info, url, ytdlp_opts)
        except Exception as e:
            await update.message.reply_text(f"خطا در دانلود: {e}")
            return

        caption = info.get("description") or "—"
        title = info.get("title") or "video"
        video_path = _find_downloaded_file(tmp)

        if not video_path:
            await update.message.reply_text("ویدیو پیدا نشد. شاید لینک خصوصی باشه.")
            return

        size = video_path.stat().st_size
        if size > TELEGRAM_MAX_BYTES:
            await update.message.reply_text("حجم ویدیو بیشتر از محدودیت تلگرامه.")
            return

        await update.message.chat.send_action(ChatAction.UPLOAD_VIDEO)
        try:
            short_caption = caption[:1024] if caption != "—" else None
            with open(video_path, "rb") as f:
                await update.message.reply_video(
                    video=f, caption=short_caption, supports_streaming=True
                )
        except Exception as e:
            await update.message.reply_text(f"خطا در ارسال ویدیو: {e}")


def _download_info(url: str, ytdlp_opts: dict) -> dict:
    with YoutubeDL(ytdlp_opts) as ydl:
        return ydl.extract_info(url, download=True)


def _find_downloaded_file(folder: Path) -> Path | None:
    exts = [".mp4", ".mkv", ".webm", ".mov", ".m4v"]
    vids = [p for p in folder.glob("*") if p.suffix.lower() in exts]
    return max(vids, key=lambda p: p.stat().st_size) if vids else None


async def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN تنظیم نشده.")

    app = Application.builder().token(token).concurrent_updates(True).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

    print("Bot is running…")
    await app.run_polling(close_loop=False)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped.")
