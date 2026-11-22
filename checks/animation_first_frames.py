"""Checks the opening frames of the Interview Python MP4s (external behaviour: only the video is looked at).

  python3 checks/animation_first_frames.py                  # every ~/animation-mp4s/py_pattern_*.mp4
  python3 checks/animation_first_frames.py a.mp4 b.mp4      # just these
  python3 checks/animation_first_frames.py --list FILE      # file names (one per line), looked up in ~/animation-mp4s

A video is flagged when, in any of its first frames (frames 0, 1, 2 and then every quarter second up to 1 s):
  (a) lesson page text is visible: bright pixels anywhere below the player's control bar (the crop is taller
      than the player while it still grows, so the page shows below it) or in the bottom strip of the frame;
      an empty dark margin below the control bar is fine;
  (b) in the first four of them (up to 0.25 s; the player starts stepping soon after) the step counter in the
      control bar does not read 1/N (the first digit is not a "1"), or is not found.
Exit status 1 if anything is flagged. Pure Python; needs ffmpeg.
"""
import glob
import os
import subprocess
import sys

W = 1600
DIR = os.path.expanduser("~/animation-mp4s")
# Frame numbers (30 fps) looked at: the very first frame, then every quarter second up to 1 s. Picked by number,
# not by a fps filter, which can skip the first frames.
PICK = (0, 1, 2, 8, 15, 23, 30)
FRAMES = len(PICK)
STRIP = 24  # rows at the bottom of the frame that must be free of page text
BRIGHT = 100  # page text is light grey on the dark page; the player's own bottom edge never exceeds this
BAR_BELOW = 14  # px from the counter text to the control bar's bottom edge (the bar's own border is dim)
# The digit "1" as the counter draws it (rows x cols, grey values), from a video known to open on 1/33.
ONE = [[19, 20, 17, 15, 36, 63, 22, 20, 20, 20], [22, 22, 33, 35, 80, 98, 23, 19, 20, 20],
       [17, 44, 93, 100, 107, 88, 24, 19, 20, 20], [17, 21, 27, 19, 64, 92, 24, 19, 20, 20],
       [19, 17, 21, 10, 61, 93, 26, 19, 21, 20], [19, 21, 20, 20, 62, 92, 26, 19, 20, 21],
       [19, 20, 20, 19, 61, 94, 26, 19, 20, 17], [20, 21, 21, 21, 63, 95, 26, 19, 20, 20],
       [19, 17, 16, 13, 55, 88, 26, 19, 21, 20], [19, 68, 97, 97, 105, 113, 100, 95, 49, 19],
       [22, 51, 70, 66, 65, 68, 71, 75, 36, 14], [15, 17, 9, 12, 12, 12, 12, 12, 12, 13]]


def frames(path):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-t", "1.3", "-vf",
                          "select='" + "+".join(f"eq(n\\,{n})" for n in PICK) + f"',scale={W}:-2",
                          "-vsync", "0", "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True,
                         stdin=subprocess.DEVNULL).stdout
    h = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip().split(",")
    H = round(int(h[1]) * W / int(h[0])) if len(h) == 2 else 0
    H -= H % 2  # scale=-2 rounds to even
    size = W * H
    return [raw[i * size:(i + 1) * size] for i in range(len(raw) // size)][:FRAMES], H


def counter_box(fr, H):
    """Rows (first, last) and first column of the counter text, or None. The counter is the only bright text
    near x 1455..1510 with empty margins left and right of it (page text runs across the whole width)."""
    ys = [y for y in range(max(H - 300, 0), H) if max(fr[y * W + 1455:y * W + 1510]) > 70]
    runs = []
    for y in ys:
        if runs and y == runs[-1][-1] + 1:
            runs[-1].append(y)
        else:
            runs.append([y])
    for r in runs:
        if all(max(fr[y * W + 1440:y * W + 1453]) <= 70 and max(fr[y * W + 1510:y * W + 1514]) <= 70 for y in r):
            x0 = next(x for x in range(1455, 1510) if max(fr[y * W + x] for y in r) > 60)
            return r[0], r[-1], x0
    return None


def corr(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    sab = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    saa, sbb = sum((x - ma) ** 2 for x in a), sum((y - mb) ** 2 for y in b)
    return sab / ((saa * sbb) ** 0.5 or 1)


def reads_one(fr, box):
    y0, _, x0 = box
    tpl = [v for row in ONE for v in row]
    best = -1
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            patch = [fr[(y0 + dy + j) * W + x0 - 1 + dx + i] for j in range(12) for i in range(10)]
            best = max(best, corr(patch, tpl))
    return best > 0.8


def problems(path):
    fs, H = frames(path)
    if len(fs) < FRAMES:
        return ["t=0: video shorter than 1 s or unreadable"]
    out = []
    for k, fr in enumerate(fs):
        t = round(PICK[k] / 30, 2)
        if max(fr[(H - STRIP) * W:]) > BRIGHT:
            out.append(f"t={t}: page text visible in the bottom strip (player cut off)")
        box = counter_box(fr, H)
        if box is None:
            out.append(f"t={t}: step counter not found")
            continue
        if max(fr[min(box[1] + BAR_BELOW, H) * W:]) > BRIGHT:
            out.append(f"t={t}: page text visible below the control bar (player cut off)")
        if PICK[k] <= 8 and not reads_one(fr, box):
            out.append(f"t={t}: step counter does not read 1/N")
    return out


def main():
    args = sys.argv[1:]
    if args[:1] == ["--list"]:
        paths = [os.path.join(DIR, n.strip()) for n in open(args[1]) if n.strip()]
    else:
        paths = args or sorted(glob.glob(os.path.join(DIR, "py_pattern_*.mp4")))
    bad = 0
    for p in paths:
        pr = problems(p)
        if pr:
            bad += 1
            print(f"FLAG {os.path.basename(p)}: " + "; ".join(sorted(set(x.split(': ', 1)[1] for x in pr))))
    print(f"{bad} flagged of {len(paths)}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
