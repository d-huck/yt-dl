import argparse
import csv
import json
import logging
import multiprocessing as mp
import os
import random
import shutil
import socket
import subprocess
import sys
import time
from multiprocessing import Process

import yt_dlp

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

ch = logging.StreamHandler()
ch.setFormatter(formatter)
ch.setLevel(logging.DEBUG)


def isOpen(ip, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        s.connect((ip, int(port)))
        s.shutdown(2)
        return True
    except:
        return False


def selectHost(hosts, args):
    while True:
        ind = random.randint(0, len(hosts) - 1)
        if isOpen("%s.%s" % (hosts[ind], args.domain), "22"):
            return hosts[ind]


def labels(label_q, args):
    start_time = time.time()
    batch_time = time.time()
    counter = 0
    data = []
    while True:
        (metadata, ytid, label_ids) = label_q.get()
        if metadata == "?":
            break

        labels = []
        video_data = {}
        if len(label_ids):
            for _id in label_ids:
                try:
                    _id = id.replace('"', "").lstrip().rstrip()
                    labels.append(_id)
                except KeyError:
                    continue
        video_data["labels"] = labels
        video_data["id"] = ytid
        if metadata:
            video_data["metadata"] = "%s.info.json" % (ytid)
        data.append(video_data)

        if counter % 128 == 0:
            end_time = time.time()
            batch_diff = end_time - batch_time
            total_diff = end_time - start_time
            logger.info(
                f"{counter}, batchtime={batch_diff:.2f}, total_time = {total_diff:.2f}"
            )
            batch_time = time.time()
        counter += 1

    logger.info(json.dump(data, f, indent=4))


def postprocess(postprocess_q, label_q, args):
    metadata = True
    while True:
        (duration, host, ytid, label_ids) = postprocess_q.get()
        if duration == "?":
            break
        else:
            os.system("mv %s/%s.info.json %s" % (args.tmp, ytid, args.out))

            in_path = "%s/%s.*" % (args.tmp, ytid)
            out_path = "%s/%s.mkv" % (args.out, ytid)
            os.system(
                "ffmpeg -nostats -loglevel 0 -hide_banner -sseof -%s -i %s %s"
                % (duration, in_path, out_path)
            )
            os.system("rm %s" % (in_path))
            label_q.put((metadata, ytid, label_ids))


def child(q, postprocess_q, child_id, args):
    while True:
        (ytid, start, duration, label_ids, host) = q.get()
        if ytid == "?":
            break

        start = time.strftime("%H:%M:%S.00", time.gmtime(start))
        duration = str(int(duration))

        try:
            output = subprocess.check_output(
                'ssh -q -o StrictHostKeyChecking=no %s@%s.%s "python3 ~/AudioSet/downloader.py %s %s %s True"'
                % (args.user, host, args.domain, ytid, start, duration),
                shell=True,
            ).decode()

        except Exception as e:
            logger.error(f"Error downloading {ytid} on {host} -- {str(e)}")
            continue

        if len(output) <= 1:
            os.system(
                "scp -q %s@%s.%s:~/AudioSet/%s.* %s"
                % (args.user, host, args.domain, ytid, args.tmp)
            )
            os.system(
                'ssh -q -o StrictHostKeyChecking=no %s@%s.%s "rm ~/AudioSet/%s.*"'
                % (args.user, host, args.domain, ytid)
            )
            postprocess_q.put((duration, host, ytid, label_ids))

        else:
            logger.error(f"{output.strip()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--data", type=str, default="", help="AudioSet data json")

    parser.add_argument(
        "--num-workers", type=int, default=5, help="number of downloading processes"
    )
    parser.add_argument(
        "--num-postprocessors",
        type=int,
        default=4,
        help="number of postprocessor processes",
    )

    parser.add_argument(
        "--user", type=str, default="", help="username on remote servers"
    )
    parser.add_argument(
        "--domain", type=str, default="", help="domain of remote servers"
    )
    parser.add_argument(
        "--hostnames", type=str, default="", help="hostnames of remote servers"
    )

    parser.add_argument("--tmp", type=str, default="", help="temporary storage")
    parser.add_argument("--out", type=str, default="", help="storage location")

    parser.add_argument(
        "--exp-dir", type=str, default="", help="directory for output files"
    )

    args = parser.parse_args()

    video_csv = args.data
    num_proxies = args.num_workers
    exp_dir = args.exp_dir
    domain = args.domain
    tmp = args.tmp
    out = args.out
    user = args.user

    # set up log files
    errh = logging.FileHandler(f"{exp_dir}/err.log")
    infoh = logging.FileHandler(f"{out.log}")

    errh.setLevel(logging.WARNING)
    infoh.setLevel(logging.INFO)

    errh.setFormatter(formatter)
    infoh.setFormatter(formatter)
    logger.addHandler(errh)
    logger.addHandler(infoh)

    q = mp.Queue()
    postprocess_q = mp.Queue()
    label_q = mp.Queue()
    num_postprocessors = args.num_postprocessors  # try for ~.8 of num_proxies
    workers = []
    hosts = []

    with open(args.hostnames, "r") as f:
        for line in f:
            if isOpen("%s.%s" % (line.strip(), domain), "22"):
                hosts.append(line.strip())

    os.system(
        'ssh -q -o StrictHostKeyChecking=no %s@%s.%s "mkdir ~/AudioSet/"'
        % (user, selectHost(hosts, args), domain)
    )
    os.system(
        "scp downloader.py %s@%s.%s:~/AudioSet/downloader.py"
        % (user, selectHost(hosts, args), domain)
    )

    for i in range(num_proxies):
        workers.append(Process(target=child, args=(q, postprocess_q, i, args)))

    for i in range(num_postprocessors):
        workers.append(Process(target=postprocess, args=(postprocess_q, label_q, args)))
    workers.append(Process(target=labels, args=(label_q, args)))

    for i in range(len(workers)):
        workers[i].start()

    start_time = time.time()
    with open(video_csv, newline="") as csvfile:
        reader = csv.reader(csvfile)

        for i, row in enumerate(reader):
            # skip header if it exists
            try:
                _ = int(row[1])
            except ValueError:
                continue

            ytid = row[0]
            start = float(row[1])
            end = float(row[2])
            duration = end - start
            label_ids = row[3:]
            host = selectHost(hosts, args)

            if not os.path.exists("%s/%s.mkv" % (tmp, ytid)):
                q.put((ytid, start, duration, label_ids, host))

    for i in range(num_proxies):
        q.put(("?", None, None, None, None))
    for i in range(num_proxies):
        workers[i].join()

    for i in range(num_postprocessors):
        postprocess_q.put(("?", None, None, None))
    for i in range(num_postprocessors):
        workers[num_proxies + i].join()
    label_q.put(("?", None, None))
    workers[len(workers) - 1].join()
    end_time = time.time()
