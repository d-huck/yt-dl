import os
import shutil
import subprocess
import sys
import tarfile
import time
from random import randint

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

MAX_LEN = 180  # 3 minute maximum

ytid = sys.argv[1]
# start = int(sys.argv[2])
# duration = int(sys.argv[3])
metadata = sys.argv[2] == "True"
home = os.path.expanduser("~")
pwd = os.getcwd()


class loggerOutputs:
    def error(msg):
        raise DownloadError(msg)

    def warning(msg):
        pass

    def debug(msg):
        pass


# print(start, duration)
base_options = {
    "cachedir": False,
    "external_downloader": {"default": "ffmpeg"},
    "external_downloader_args": {
        "ffmpeg": [
            "-nostats",
            "-loglevel",
            "panic",
            "-hide_banner",
        ]
    },
    "extract_flat": "discard_in_playlist",
    "extractor_args": {"youtube": {"skip": ["hls", "dash"]}},
    "format": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "fragment_retries": 10,
    # "ignoreerrors": "only_download",
    "merge_output_format": "mkv",
    "no_warnings": True,
    "noprogress": True,
    "outtmpl": {"default": f"~/AudioSet/{ytid}/%(id)s.%(ext)s"},
    "overwrites": False,
    "postprocessors": [
        {"key": "FFmpegConcat", "only_multi_video": True, "when": "playlist"}
    ],
    "quiet": True,
    # "logger": loggerOutputs,
    "retries": 5,
    "socket_timeout": 60.0,
    "throttledratelimit": 5_120_000,
    "writeinfojson": True,
}


def detect_crop(fp):
    command = f"ffmpeg -hide_banner -i {fp} -vf 'cropdetect' -f null -"
    command = command.split()
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = result.stdout.decode("utf-8")
    output = list(filter(lambda x: "Parsed_cropdetect" in x, output.split("\n")))
    crop_param = output[-1].split(" ")[-1]
    dims = [int(x) for x in crop_param[5:].split(":")[:2]]
    return dims


def split_video(result, t=10, n=4):
    start = 0
    duration = int(result["duration"])
    fname = os.path.join(home, f"AudioSet/{ytid}/{ytid}.mkv")
    try:
        dim = detect_crop(fname)
    except (
        IndexError
    ):  # if crop detection fails, just center crop to standard resolution
        dim = [960, 720]

    if duration > MAX_LEN and start == 0:
        start = (duration - MAX_LEN) // 2
        duration = start + MAX_LEN
    segment_length = duration // n
    for i, st in enumerate(range(start, duration, segment_length)):
        if i == n:
            break
        s = randint(st, st + segment_length - t)
        #    for i, start in enumerate(range(start, int(duration), t)):
        os.system(
            f"ffmpeg -hide_banner -loglevel 0 -i {fname} -ss {s} -t {t} -vf 'fps=24,crop={dim[0]}:{dim[1]}' -reset_timestamps 1 -c:v libx264 -crf 23 -preset veryfast -ac 1 -ar 48000 ~/AudioSet/{ytid}/{ytid}.{i:03d}.mkv"
        )
    os.remove(fname)
    tgz_fname = os.path.join(home, f"AudioSet/{ytid}.tgz")
    folder = os.path.join(home, f"AudioSet/{ytid}")
    with tarfile.open(tgz_fname, "w:gz") as tar:
        tar.add(folder, arcname=os.path.basename(f"AudioSet/{ytid}"))
    shutil.rmtree(folder)


with YoutubeDL(base_options) as ydl:
    try:
        result = ydl.extract_info(ytid, download=False)
        if result["height"] >= 720:
            ydl.download(ytid)
            split_video(result)
    except DownloadError as e:
        print(f"Unable to download {ytid} on {os.uname()[1]}: {e}")
