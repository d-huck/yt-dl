import sys
import time
import os
import yt_dlp
from yt_dlp import YoutubeDL
import time
import random
import subprocess

ytid = sys.argv[1]
start = sys.argv[2]
duration = sys.argv[3]
metadata = sys.argv[4] == "True"

base_options = {
    "cachedir": False,
    "external_downloader": {"default": "ffmpeg"},
    "external_downloader_args": {
        "ffmpeg_i": [
            "-nostats",
            "-loglevel",
            "panic",
            "-hide_banner",
            "-ss",
            start,
            "-t",
            duration,
        ]
    },
    "extract_flat": "discard_in_playlist",
    "extractor_args": {"youtube": {"skip": ["hls", "dash"]}},
    "format": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "fragment_retries": 10,
    "ignoreerrors": "only_download",
    "merge_output_format": "mkv",
    "no_warnings": True,
    "noprogress": True,
    "outtmpl": {"default": "~/AudioSet/%(id)s.%(ext)s"},
    "overwrites": False,
    "postprocessors": [
        {"key": "FFmpegConcat", "only_multi_video": True, "when": "playlist"}
    ],
    "quiet": True,
    "retries": 5,
    "socket_timeout": 60.0,
    "throttledratelimit": 102400,
    "writeinfojson": True,
}


with YoutubeDL(base_options) as ydl:
    error = ydl.download(ytid)
    if error:
        print(f"Unable to download {ytid} on {os.uname()[1]} -- error code: {error}")
