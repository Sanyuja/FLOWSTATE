#!/usr/bin/env python3
"""
reel_creator.py -- AI Reel Assembler
Deploy to: YOUR_SCRIPTS_DIR\\reel_creator.py  (set via SCRIPTS_DIR env var)

Uses FFmpeg for maximum reliability on Windows.
Handles: 9:16 crop, resize, clip trimming, xfade transitions,
         voiceover mixing, caption burn-in, final export.

Called by the n8n reel_creator workflow via Execute Command node.

Usage:
  python reel_creator.py --args "D:\\your-content\\scripts\\reel_args_temp.json"

Input JSON structure (reel_args_temp.json):
{
  "clips": ["D:\\path\\clip1.mp4", "D:\\path\\clip2.mp4"],
  "duration": 30,
  "outputPath": "D:\\your-content_vault\\reel_review\\output.mp4",
  "voiceoverPath": "D:\\path\\voiceover.mp3",
  "voiceoverScript": "Your voiceover text for caption burn-in",
  "style": "smooth"
}

Styles: smooth | energetic | slow_burn | dramatic
"""

import sys
import json
import os
import subprocess
import shutil
from pathlib import Path


def log(msg):
    print(f"[reel_creator] {msg}", flush=True)


def run_ffmpeg(cmd, timeout=120, label=""):
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            log(f"FFmpeg error ({label}): {result.stderr[-600:]}")
            return False, result.stderr
        return True, ""
    except subprocess.TimeoutExpired:
        log(f"FFmpeg timeout ({label}) after {timeout}s")
        return False, "timeout"
    except Exception as e:
        log(f"FFmpeg exception ({label}): {e}")
        return False, str(e)


def get_video_info(path):
    try:
        r = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration",
            "-show_entries", "format=duration",
            "-of", "json", path
        ], capture_output=True, text=True, timeout=15)
        data = json.loads(r.stdout)
        streams = data.get("streams", [{}])
        fmt = data.get("format", {})
        w = streams[0].get("width") if streams else None
        h = streams[0].get("height") if streams else None
        dur = float(streams[0].get("duration") or fmt.get("duration") or 0)
        return dur, w, h
    except Exception as e:
        log(f"ffprobe failed for {path}: {e}")
        return None, None, None


def crop_and_prepare_clip(src, dst, start, duration, fade_in, fade_out, w, h):
    target_ratio = 9 / 16
    src_ratio = w / h if h else 1.0

    if src_ratio > target_ratio:
        new_w = int(h * target_ratio)
        cx = (w - new_w) // 2
        crop = f"crop={new_w}:{h}:{cx}:0"
    elif src_ratio < target_ratio:
        new_h = int(w / target_ratio)
        cy = (h - new_h) // 2
        crop = f"crop={w}:{new_h}:0:{cy}"
    else:
        crop = f"crop={w}:{h}:0:0"

    vf_parts = [crop, "scale=1080:1920:flags=lanczos", "setsar=1"]
    if fade_in > 0:
        vf_parts.append(f"fade=t=in:st=0:d={fade_in:.2f}")
    if fade_out > 0:
        fo_start = max(0, duration - fade_out)
        vf_parts.append(f"fade=t=out:st={fo_start:.2f}:d={fade_out:.2f}")

    vf = ",".join(vf_parts)

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(round(start, 3)),
        "-i", src,
        "-t", str(round(duration, 3)),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-ar", "44100", "-ac", "2",
        "-avoid_negative_ts", "make_zero",
        "-movflags", "+faststart",
        dst
    ]
    ok, _ = run_ffmpeg(cmd, timeout=90, label=f"prepare:{os.path.basename(src)}")
    return ok


def xfade_two_clips(clip_a, clip_b, out, a_duration, transition_dur, transition_type="fade"):
    offset = max(0.01, a_duration - transition_dur)
    vf = (
        f"[0:v][1:v]xfade=transition={transition_type}"
        f":duration={transition_dur:.2f}:offset={offset:.2f}[v];"
        f"[0:a][1:a]acrossfade=d={transition_dur:.2f}[a]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", clip_a, "-i", clip_b,
        "-filter_complex", vf,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac",
        "-movflags", "+faststart",
        out
    ]
    ok, _ = run_ffmpeg(cmd, timeout=120, label="xfade")
    return ok


def chain_xfades(prepared_clips, clip_durations, transition_dur, transition_type, temp_dir):
    if len(prepared_clips) == 1:
        return prepared_clips[0]

    current = prepared_clips[0]
    current_dur = clip_durations[0]

    for i in range(1, len(prepared_clips)):
        out = os.path.join(temp_dir, f"xfade_{i:02d}.mp4")
        ok = xfade_two_clips(current, prepared_clips[i], out, current_dur, transition_dur, transition_type)
        if ok:
            current = out
            current_dur = current_dur + clip_durations[i] - transition_dur
        else:
            log(f"xfade failed at clip {i}, skipping transition")
    return current


def add_voiceover(video, vo_audio, out, vo_vol=0.95, bg_vol=0.12):
    fc = (
        f"[0:a]volume={bg_vol}[bg];"
        f"[1:a]volume={vo_vol}[vo];"
        f"[bg][vo]amix=inputs=2:duration=shortest:dropout_transition=0[aout]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", video, "-i", vo_audio,
        "-filter_complex", fc,
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac",
        "-shortest", out
    ]
    ok, _ = run_ffmpeg(cmd, timeout=120, label="voiceover")
    return ok


def build_caption_srt(script_text, total_duration):
    if not script_text or not script_text.strip():
        return ""

    words = script_text.split()
    chunk_size = 7
    chunks = [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]
    if not chunks:
        return ""

    seg_dur = total_duration / len(chunks)
    lines = []
    for idx, chunk in enumerate(chunks):
        start_s = idx * seg_dur
        end_s   = (idx + 1) * seg_dur - 0.05

        def fmt_time(s):
            h = int(s // 3600)
            m = int((s % 3600) // 60)
            sec = s % 60
            return f"{h:02d}:{m:02d}:{sec:06.3f}".replace(".", ",")

        lines.append(f"{idx+1}\n{fmt_time(start_s)} --> {fmt_time(end_s)}\n{chunk}\n")

    return "\n".join(lines)


def burn_captions(video, srt_path, out):
    srt_escaped = srt_path.replace("\\", "/").replace(":", "\\:")
    vf = (
        f"subtitles='{srt_escaped}'"
        f":force_style='FontName=Arial,FontSize=52,PrimaryColour=&HFFFFFF,"
        f"OutlineColour=&H000000,Outline=3,Bold=1,"
        f"Alignment=2,MarginV=60'"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", video,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "copy",
        out
    ]
    ok, err = run_ffmpeg(cmd, timeout=180, label="captions")
    return ok


def main():
    if len(sys.argv) < 3 or sys.argv[1] != "--args":
        print(json.dumps({"error": "Usage: reel_creator.py --args <args_file.json>"}))
        sys.exit(1)

    args_path = sys.argv[2]
    with open(args_path, "r", encoding="utf-8") as f:
        args = json.load(f)

    clips            = args.get("clips", [])
    target_duration  = float(args.get("duration", 30))
    output_path      = args.get("outputPath")
    voiceover_path   = args.get("voiceoverPath") or None
    voiceover_script = args.get("voiceoverScript", "")
    style            = args.get("style", "smooth")

    if not output_path:
        vault = os.environ.get("VAULT_BASE", "D:\\content_vault")
        output_path = os.path.join(vault, "reel_review", "reel_output.mp4")

    style_map = {
        "slow_burn":  {"transition": 0.8, "type": "fade",       "start_offset": 0.15},
        "smooth":     {"transition": 0.5, "type": "fade",       "start_offset": 0.10},
        "energetic":  {"transition": 0.2, "type": "slideleft",  "start_offset": 0.05},
        "dramatic":   {"transition": 1.0, "type": "fadeblack",  "start_offset": 0.20},
    }
    st = style_map.get(style, style_map["smooth"])
    transition_dur  = st["transition"]
    transition_type = st["type"]
    start_offset    = st["start_offset"]

    log(f"Style: {style} | Transition: {transition_dur}s {transition_type} | Clips: {len(clips)} | Target: {target_duration}s")

    if not clips:
        print(json.dumps({"error": "No clips provided"}))
        sys.exit(1)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    temp_dir = os.path.join(os.path.dirname(output_path), "_reel_temp")
    os.makedirs(temp_dir, exist_ok=True)

    valid_clips = []
    for cp in clips:
        if not os.path.exists(cp):
            log(f"Missing clip: {cp}")
            continue
        dur, w, h = get_video_info(cp)
        if dur and dur > 1.0 and w and h:
            valid_clips.append({"path": cp, "duration": dur, "w": w, "h": h})
        else:
            log(f"Unusable clip: {cp}")

    if not valid_clips:
        print(json.dumps({"error": "No valid clips after probing"}))
        sys.exit(1)

    n = len(valid_clips)
    clip_budget = (target_duration + (n - 1) * transition_dur) / n
    clip_budget = max(2.0, min(clip_budget, 12.0))
    log(f"Clip budget: {clip_budget:.2f}s each ({n} clips)")

    prepared = []
    prepared_durations = []

    for i, c in enumerate(valid_clips):
        src      = c["path"]
        dur      = c["duration"]
        w, h     = c["w"], c["h"]

        safe_start = min(dur * start_offset, 2.0)
        available  = dur - safe_start
        take       = min(clip_budget, available)

        if take < 1.0:
            log(f"Clip {i+1} too short after offset, skipping")
            continue

        fade_in  = transition_dur if i > 0 else 0.3
        fade_out = transition_dur if i < n - 1 else 0.3

        dst = os.path.join(temp_dir, f"prep_{i:02d}.mp4")
        ok  = crop_and_prepare_clip(src, dst, safe_start, take, fade_in, fade_out, w, h)

        if ok:
            prepared.append(dst)
            prepared_durations.append(take)
            log(f"Clip {i+1}/{n}: {os.path.basename(src)} ({take:.1f}s)")
        else:
            log(f"Clip {i+1}/{n} failed, skipping")

    if not prepared:
        print(json.dumps({"error": "All clips failed processing"}))
        sys.exit(1)

    log("Applying transitions...")
    chained = chain_xfades(prepared, prepared_durations, transition_dur, transition_type, temp_dir)

    current = chained
    if voiceover_path and os.path.exists(voiceover_path):
        log("Mixing voiceover...")
        vo_out = os.path.join(temp_dir, "with_vo.mp4")
        if add_voiceover(current, voiceover_path, vo_out):
            current = vo_out
            log("Voiceover mixed")
        else:
            log("Voiceover failed -- continuing without it")

    if voiceover_script and voiceover_script.strip():
        log("Generating captions...")
        actual_dur, _, _ = get_video_info(current)
        actual_dur = actual_dur or target_duration
        srt_content = build_caption_srt(voiceover_script, actual_dur)

        if srt_content:
            srt_path = os.path.join(temp_dir, "captions.srt")
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_content)

            cap_out = os.path.join(temp_dir, "with_captions.mp4")
            if burn_captions(current, srt_path, cap_out):
                current = cap_out
                log("Captions burned in")
            else:
                log("Captions failed -- continuing without them")

    shutil.copy2(current, output_path)

    try:
        shutil.rmtree(temp_dir)
    except Exception as e:
        log(f"Cleanup warning: {e}")

    final_dur, _, _ = get_video_info(output_path)
    size_mb = os.path.getsize(output_path) / (1024 * 1024)

    result = {
        "success":        True,
        "outputPath":     output_path,
        "duration":       round(final_dur or target_duration, 1),
        "sizeMB":         round(size_mb, 1),
        "clipsUsed":      len(prepared),
        "voiceoverAdded": bool(voiceover_path and os.path.exists(voiceover_path or "")),
        "captionsAdded":  bool(voiceover_script and voiceover_script.strip()),
    }

    log(f"Done: {output_path} | {size_mb:.1f}MB | {final_dur:.1f}s")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
