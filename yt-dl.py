import argparse
import csv
import json
import logging
import multiprocessing as mp
import os
import random
import socket
import subprocess
import time
from multiprocessing import Process


# from tqdm.contrib.logging import logging_redirect_tqdm

logger = logging.getLogger(__name__)


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
                    _id = _id.replace('"', "").lstrip().rstrip()
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

    with open("%s/out.json" % (args.out), "a") as f:
        json.dump(data, f, indent=4)


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
                "ffmpeg -nostats -loglevel 0 -hide_banner -threads 2 -sseof -%s -i %s %s"
                % (duration, in_path, out_path)
            )
            os.system("rm -rf %s" % (in_path))
            label_q.put((metadata, ytid, label_ids))


def cleanup(usr, host, dom, ytid):
    os.system(
        f'ssh -q -o StrictHostKeyChecking=no {usr}@{host}.{dom} rm -rf "~/AudioSet/{ytid}.* {ytid}/"'
    )


def child(q, postprocess_q, child_id, done_q, args):
    while True:
        (ytid, start, duration, label_ids, host) = q.get()
        if ytid == "?":
            logger.info(f"Queue empty, child #{child_id} finished!")
            break

        # start = time.strftime("%H:%M:%S.00", time.gmtime(start))
        duration = str(int(duration))

        try:
            logger.info(f"[qsize: {q.qsize()}] Downloading {ytid} on {host}")
            output = subprocess.check_output(
                'ssh -q -o StrictHostKeyChecking=no %s@%s.%s "python3 ~/AudioSet/downloader.py %s %s %s True"'
                % (args.user, host, args.domain, ytid, start, duration),
                shell=True,
            ).decode()

        except Exception as e:
            logger.error(f"Error downloading {ytid} on {host} -- {str(e)}")
            done_q.put(1)
            continue

        if len(output) <= 1:
            out_dir = args.tmp if args.postprocess else args.out
            if ytid.startswith("-"):
                ytid = "\\" + ytid
            os.system(
                f'scp -q {args.user}@{host}.{args.domain}:"~/AudioSet/{ytid}.tgz" {out_dir}'
            )
            cleanup(args.user, host, args.domain, ytid)
            if args.postprocess:
                postprocess_q.put((duration, host, ytid, label_ids))

        else:
            logger.error(f"Error: {output.strip()}")
        done_q.put(1)


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

    parser.add_argument("--tmp", type=str, default="./tmp", help="temporary storage")
    parser.add_argument("--out", type=str, default="./data", help="storage location")

    parser.add_argument(
        "--exp-dir", type=str, default="./logs", help="directory for output files"
    )
    parser.add_argument(
        "--postprocess",
        type=bool,
        default=False,
        help="post process by enforcing duration",
    )
    parser.add_argument(
        "--datatype",
        type=str,
        default="csv",
        help="What kind of structure is the input file? choices are csv (default) and tsv",
    )

    args = parser.parse_args()

    delim = ","
    if args.datatype == "tsv":
        delim = "\t"

    video_csv = args.data
    num_proxies = args.num_workers
    exp_dir = args.exp_dir
    domain = args.domain
    tmp = args.tmp
    out = args.out
    user = args.user

    if not os.path.exists(tmp):
        os.makedirs(tmp)
    if not os.path.exists(out):
        os.makedirs(out)
    if not os.path.exists(exp_dir):
        os.makedirs(exp_dir)

    # set up logging
    logger = logging.getLogger("yt_dl")
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s ::%(levelname)s:: %(message)s")

    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    ch.setLevel(logging.INFO)

    error_handler = logging.FileHandler(
        f"{args.exp_dir}/err.log",
        mode="w",
    )
    info_handler = logging.FileHandler(f"{args.exp_dir}/out.log", mode="w")
    error_handler.setLevel(logging.ERROR)
    info_handler.setLevel(logging.INFO)
    error_handler.setFormatter(formatter)
    info_handler.setFormatter(formatter)
    logger.addHandler(error_handler)
    logger.addHandler(info_handler)
    logger.addHandler(ch)

    q = mp.Queue()
    postprocess_q = mp.Queue()
    label_q = mp.Queue()
    done_q = mp.Queue()
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

    logger.info("Setting up workers...")
    for i in range(num_proxies):
        workers.append(Process(target=child, args=(q, postprocess_q, i, done_q, args)))

    if args.postprocess:

        logger.info("Setting up postprocessors...")
        for i in range(num_postprocessors):
            workers.append(
                Process(target=postprocess, args=(postprocess_q, label_q, args))
            )
        workers.append(Process(target=labels, args=(label_q, args)))
    else:
        del postprocess_q
        del label_q

    for i in range(len(workers)):
        workers[i].start()

    start_time = time.time()
    completed = []
    for root, dirs, files in os.walk(out):
        for file in files:
            if file.endswith(".tgz"):
                completed.append(file.split(".")[0])

    videos = []

    logger.info("Reading video csv...")
    with open(video_csv, newline="") as csvfile:
        reader = csv.reader(csvfile, delimiter=delim)
        for i, row in enumerate(reader):
            # skip header if it exists
            try:
                start = int(row[1])
            except ValueError:
                continue

            ytid = row[0]
            if ytid in completed:  # skip if already downloaded
                continue

            end = int(row[2])
            duration = end - start
            label_ids = row[3:]
            host = selectHost(hosts, args)

            if not os.path.exists("%s/%s.mkv" % (tmp, ytid)):
                q.put((ytid, start, duration, label_ids, host))

    for i in range(num_proxies):
        q.put(("?", None, None, None, None))
    try:
        for i in range(num_proxies):
            workers[i].join()
        if args.postprocess:
            for i in range(num_postprocessors):
                postprocess_q.put(("?", None, None, None))
            for i in range(num_postprocessors):
                workers[num_proxies + i].join()
            label_q.put(("?", None, None))
        for worker in workers:
            worker.join()
    except KeyboardInterrupt:
        for worker in workers:
            worker.terminate()
    end_time = time.time()
