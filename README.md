# yt-dl

This project implements a massively parallel downloader based on the yt-dlp fork of youtube-dl. We avoid throttling/ip blacklisting by downloading the videos through remote servers. Using a large number of servers ensures that no individual machine downloads too frequently.

Unlike prior work, this fork of the project generalizes to simple youtube IDs without focusing specifically on AudioSet.

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
