#!/usr/bin/env python3
"""
downloader.py

Downloads the best audio from a YouTube URL and converts it to MP3.
Designed to be run inside a GitHub Actions runner where the URL is passed
via an environment variable or CLI argument and the generated MP3 is placed
into an `artifacts/` directory for uploading by the workflow.

Usage:
  python downloader.py "https://youtube.com/watch?v=..."

Or set environment variable `YOUTUBE_URL` and run `python downloader.py`.
"""

from __future__ import annotations

import os
import sys
import logging
import tempfile
import shutil
import glob
from pathlib import Path
from typing import Optional

import yt_dlp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("downloader")


def find_latest_mp3(directory: str) -> Optional[str]:
    mp3s = glob.glob(os.path.join(directory, "*.mp3"))
    if not mp3s:
        return None
    mp3s.sort(key=os.path.getmtime, reverse=True)
    return mp3s[0]


def download_to_mp3(url: str, out_dir: str) -> str:
    """Download best audio for `url` and convert to MP3 inside `out_dir`.

    Returns the path to the created MP3 file.
    Raises RuntimeError on failure.
    """
    os.makedirs(out_dir, exist_ok=True)

    ytdl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(out_dir, "%(title)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }
        ],
    }

    try:
        with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
            logger.info("Starting download for %s", url)
            info = ydl.extract_info(url, download=True)
            logger.info("Download complete: %s", info.get("title"))
    except yt_dlp.utils.DownloadError as e:
        logger.exception("yt-dlp DownloadError")
        raise RuntimeError(f"Download failed: {e}") from e
    except Exception as e:
        logger.exception("Unexpected error from yt-dlp")
        raise RuntimeError("Unexpected download error") from e

    mp3_path = find_latest_mp3(out_dir)
    if not mp3_path:
        raise RuntimeError("MP3 not found after conversion")

    return mp3_path


def main(argv: list[str]) -> int:
    # Priority: CLI arg > env var
    url = None
    if len(argv) >= 2 and argv[1].strip():
        url = argv[1].strip()
    else:
        url = os.environ.get("YOUTUBE_URL") or os.environ.get("INPUT_YOUTUBE_URL")

    if not url:
        logger.error("No YouTube URL provided. Set YOUTUBE_URL or pass as argument.")
        print("ERROR: No YouTube URL provided. Set YOUTUBE_URL or pass as argument.")
        return 2

    # Make a temporary work directory to isolate yt-dlp artifacts
    workdir = tempfile.mkdtemp(prefix="yt-dlp-")
    artifacts_dir = os.path.abspath("artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)

    try:
        mp3_path = download_to_mp3(url, workdir)

        # Move mp3 to artifacts directory
        dest = Path(artifacts_dir) / Path(mp3_path).name
        shutil.move(mp3_path, dest)
        logger.info("MP3 saved to %s", dest)

        # Print artifact path for workflow logs
        print(f"ARTIFACT_MP3={dest}")
        return 0

    except RuntimeError as e:
        logger.error("Failed: %s", e)
        print(f"ERROR: {e}")
        return 3
    finally:
        # Cleanup temp dir
        try:
            shutil.rmtree(workdir)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
