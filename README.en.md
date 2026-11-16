# Viral Clip Cutter

Automatically cuts short clips out of a long video: detects scene boundaries, cuts
fragments of the length you want, optionally adds speech subtitles and converts the
picture to a vertical format for Reels, Shorts and TikTok.

Runs locally on Windows and does not upload your video anywhere.

**Language / Язык:** English | [Русский](README.md)

---

## What it does

- Cuts video by scene changes or into equal parts of a fixed length.
- Enforces clip length limits: not shorter and not longer than set values.
- Recognizes speech and generates subtitles (if the recognition package is installed).
- Smart reframing: keeps the main subject in frame when converting to vertical.
- Burns in a title and an overlay for a specific platform.
- Can add background music.
- Can download the source by link (YouTube and others) through yt-dlp.
- Has a GUI: `gui.py`.
- Writes a report and a log into the output folder.

---

## Requirements

1. Python 3.10 or newer.
2. ffmpeg, the video tool. Download from https://ffmpeg.org/download.html, unpack it and
   add its `bin` folder to the PATH environment variable.
   Check: run `ffmpeg -version` in a terminal, it must print a version.
3. Python packages:

```
pip install opencv-python numpy requests
```

Optional:

```
pip install yt-dlp
pip install SpeechRecognition
```

- `yt-dlp` is needed only when downloading by link.
- `SpeechRecognition` is needed only when you want subtitles.

---

## Quick start

```
python viral_clip_cutter.py -i "C:\video\lecture.mp4" -o "C:\video\clips"
```

Result: the folder `C:\video\clips` with finished fragments and a log.

With the GUI:

```
python gui.py
```

---

## Command line options

| Option | Meaning |
|---|---|
| `-i`, `--input` | path to the video or a link (required) |
| `-o`, `--output` | output folder, default `clips` |
| `-t`, `--threshold` | scene change detection sensitivity |
| `-min` | minimum clip length in seconds |
| `-max` | maximum clip length in seconds |
| `-f`, `--format` | output format and resolution |
| `-T`, `--title` | burn a title into the video |
| `-w`, `--workers` | how many clips to process in parallel |
| `-v`, `--verbose` | verbose console output |
| `-e`, `--equal-parts` | cut into equal parts |
| `-p`, `--part-duration` | length of an equal part in seconds |
| `-s`, `--subtitles` | generate subtitles from speech |
| `--template` | overlay template: tiktok, instagram and others from the code |
| `-r`, `--smart-reframe` | smart reframing for vertical video |
| `-m`, `--music` | add background music |
| `--music-file` | path to the music file |
| `--preview` | fast preview without full processing |
| `--viral-boost` | stronger settings aimed at short clips |
| `--auto-fallback` | fall back to a backup method if the main one fails |
| `--command-timeout` | time limit for a single ffmpeg command, seconds |

Examples:

```
python viral_clip_cutter.py -i "D:\video\podcast.mp4" -o "D:\clips" -min 15 -max 60
python viral_clip_cutter.py -i "D:\video\webinar.mp4" -o "D:\clips" -e -p 30
python viral_clip_cutter.py -i "D:\video\talk.mp4" -o "D:\clips" -r -f 1080x1920 -s
```

---

## Files

| File | Purpose |
|---|---|
| `viral_clip_cutter.py` | main version |
| `enhanced_viral_clip_cutter_timeout.py` | version with ffmpeg timeouts: does not hang on a broken file |
| `gui.py` | graphical interface |
| `LICENSE` | usage terms |

---

## Troubleshooting

**`ffmpeg not found`** - ffmpeg is not in PATH. Check `ffmpeg -version` in a terminal.

**Non-ASCII path breaks processing** - put the video into a folder with a Latin name,
for example `C:\video\src.mp4`, and write the result there too.

**Clips are too choppy** - lower `-t` (sensitivity) or use `-e -p` to cut into equal parts.

**No subtitles** - `SpeechRecognition` is not installed or the video has no speech.

---

## Limitations

- The script targets Windows: part of the code uses Windows system calls.
- Downloading by link goes through yt-dlp; on some platforms this violates their terms,
  and the user is responsible for how it is used.
- Processing is local, the network is used only to download the source.

---

## License

See the [LICENSE](LICENSE) file.