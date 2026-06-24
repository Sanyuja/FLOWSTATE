# Reel Creator Guide

The reel creator assembles short-form video automatically from your existing clips. You send a concept via WhatsApp, it builds a reel and sends you a preview. You approve or skip.

---

## Triggering a reel

Send this via WhatsApp:

```
IDEA: [content description], [mood/style], [duration]s [VO or no VO]
```

**Examples:**

```
IDEA: dance, moody red light, 20s VO
IDEA: lifestyle, golden hour vibes, 30s no VO
IDEA: fitness, energetic, 15s VO
IDEA: coffee morning, cozy slow, 25s no VO
```

- `VO` = include AI-generated voiceover (OpenAI TTS nova voice)
- `no VO` = music only, no narration

---

## What happens

1. GPT-4o parses your IDEA message into a structured spec (folder, duration, style, voiceover script)
2. GPT-4o Vision scores clips in your content folder for quality and mood match
3. If VO requested: GPT-4o writes the voiceover script, OpenAI TTS generates the audio
4. `reel_creator.py` assembles via FFmpeg:
   - Crops each clip to 9:16 (1080x1920)
   - Trims to time budget per clip
   - Applies xfade transitions
   - Mixes voiceover over background audio (ducks background to 12%)
   - Burns captions from voiceover script (white text, bottom-centered)
5. Assembled reel uploads to Imgur
6. WhatsApp sends you the preview link + music suggestion

---

## Your replies

| Reply | What happens |
|---|---|
| `POST` | Uploads to Instagram Reels + Threads |
| `REDO` | Triggers new assembly with different clip selection |
| `SKIP` | Discards the reel |

---

## Styles

| Style | Transition | Effect |
|---|---|---|
| `smooth` | 0.5s fade | Default. Clean, polished |
| `energetic` | 0.2s slide | Fast cuts, high energy |
| `slow_burn` | 0.8s fade | Slow, cinematic |
| `dramatic` | 1.0s fade to black | Moody, cinematic |

If you don't specify a style, FLOWSTATE picks based on your content description (dance/fitness -> energetic, lifestyle/coffee -> smooth, night/moody -> dramatic).

---

## Voiceover details

- **Voice:** OpenAI TTS, nova voice at 0.92x speed
- **Script:** Written by GPT-4o based on your IDEA description and voice brief
- **Captions:** Automatically generated from the voiceover script, timed evenly across the video
- **Caption style:** White text, Arial bold, bottom-centered, black outline

To use your own voiceover instead of AI-generated: drop the audio file into your scripts folder and reference it in a custom IDEA message.

---

## Where files go

```
Reel assembly temp files: VAULT_BASE\reel_review\_reel_temp\  (auto-deleted after assembly)
Finished reel:            VAULT_BASE\reel_review\reel_output.mp4
After approval + post:    APPROVED_BASE\instagram\
                          APPROVED_BASE\threads\
```

---

## Troubleshooting

**No WhatsApp response after sending IDEA**
- Check that the reel_creator workflow is activated in n8n
- Check that ngrok is running and the webhook URL is set correctly in Twilio
- Check n8n execution logs for the reel-handler webhook

**Reel assembly fails**
- Check that FFmpeg is installed and in PATH: run `ffmpeg -version` in PowerShell
- Check that `reel_creator.py` is in your SCRIPTS_DIR
- Check n8n execution logs for the Execute Command node

**Clips not found**
- The folder name in your IDEA message must match a folder in your CONTENT_BASE
- Check that the clips are video files (mp4, mov, avi) not images

**Captions look wrong**
- Voiceover script is split into ~7-word chunks timed evenly
- For better caption timing, send shorter, punchier voiceover ideas

---

## Dependencies

- FFmpeg in PATH (auto-installed by `install_reel_deps.ps1` via winget)
- Python 3.10+ with no additional packages required (uses stdlib only)
- `reel_creator.py` deployed to SCRIPTS_DIR (done by `install_reel_deps.ps1`)
