# yt-dl

This project implements a massively parallel downloader based on the yt-dlp fork of youtube-dl. We avoid throttling/ip blacklisting by downloading the videos through remote servers. Using a large number of servers ensures that no individual machine downloads too frequently.

The script accepts simple inputs from a dataset, such as [YouTube-8M](https://research.google.com/youtube8m/) as a csv where the first column is the video ID, and the remaining columns represent any number of labels. The orchestrator will launch a thread on a remote machine, download the video and divide it into $n$ 10-second chunks evenly distributed across the video. All rendering and chopping work occurs on the remote servers before being zipped and returned to the orchestrating machine.

### Dependencies

- Python 3.8+
- yt-dlp (https://github.com/yt-dlp/yt-dlp)
- ffmpeg

In addition, you should have passowordless ssh privileges to servers.

### Usage

```
python3 yt-dl.py [OPTIONS]
```

### Options

    --data                           AudioSet data csv location
    <!-- --ontology                       AudioSet ontology json location -->
    --num-workers                    Number of downloading processes
    --postprocess                    Turn postprocessing on/off. Default off
    --num-postprocessers             Number of postprocessor processes
    --user                           Username on remote servers
    --domain                         Domain of remote servers
    --hostnames                      Hostnames of remote servers
    --tmp                            Temporary storage location [Default: ./tmp]
    --out                            Output directory [Default: ./data]
    --exp_dir                        Logfile directory [Default: ./logs]
    --datatype                       Specify 'csv' or 'tsv' [Default: 'csv']
