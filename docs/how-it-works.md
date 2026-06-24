# How FLOWSTATE Works

## System overview

FLOWSTATE runs entirely on your own machine. There is no cloud service, no SaaS subscription, no external platform storing your content. Everything runs locally via n8n, with only the API calls (OpenAI, Twilio, platform APIs) going out.

```
Your PC (always-on)
│
├── n8n (localhost:5678)
│   ├── Image Pipeline workflow
│   ├── Approval Handler workflow
│   └── Reel Creator workflow
│
├── Your content folders
│   ├── [persona]/dance/
│   ├── [persona]/lifestyle/
│   ├── [persona]/coffee/
│   └── [persona]/nsfw/  <- vault only, never posted
│
└── Scripts
    ├── blur.js
    └── reel_creator.py
```

---

## Image pipeline (step by step)

**1. File watcher**
n8n watches your content folder recursively. The moment a file lands, it triggers.

**2. Routing check**
Files in `_approved`, `_vault`, or `scripts` subfolders are ignored (these are output folders, not input).

**3. File type check**
Images go to the image pipeline. Videos are handled separately (either via reel creator or skipped based on your config).

**4. Get file context**
The filename and parent folder name are extracted. The folder name maps to your configured blur level and vault rules.

**5. Vault-only check**
If the folder is flagged `vault_only` in your persona config (e.g. an `nsfw` folder), the file is copied directly to your vault and never reaches approval. No AI analysis, no posting.

**6. Vision + blur**
For all other content, GPT-4o Vision analyses the image and returns bounding boxes for regions that need blurring based on your blur level setting. Sharp.js applies Gaussian blur to those regions and saves the result to your `_approved/instagram/` folder. The unblurred original is copied to your vault.

**7. Caption generation**
GPT-4o writes 3 caption options in your persona's voice (defined in your voice brief). It also generates hashtags and a suggested posting time based on the content folder.

**8. WhatsApp approval**
Twilio sends you a WhatsApp message with:
- The content category and suggested post time
- All 3 caption options
- Reply instructions: Y1 / Y2 / Y3 / N / E

The pending approval is saved to `pending_approvals.json`.

---

## Approval handler (step by step)

**1. Incoming webhook**
Twilio sends a POST to your ngrok URL when you reply. n8n receives it.

**2. Parse reply**
- `Y1` / `Y2` / `Y3` -- approve with that caption
- `N` -- skip, mark as rejected
- `E` -- edit mode, prompts you to send your own caption

**3. Load pending approval**
The approval ID (stored in `pending_approvals.json`) is matched to retrieve the image path, captions, and hashtags.

**4. Upload to Imgur**
The blurred image is uploaded to Imgur to get a public URL. Instagram and Threads require a publicly accessible URL to pull media from.

**5. Post to platforms**
- **Instagram:** Two-step Graph API call -- create container, publish. Hashtags are posted as a first comment.
- **Threads:** Same two-step pattern via Threads API.
- **X/Twitter:** Caption is included in the WhatsApp confirmation so you can paste it manually.

**6. Confirmation**
WhatsApp sends you a confirmation message with the live post link.

---

## Reel creator (step by step)

**1. IDEA message**
You send `IDEA: [description]` via WhatsApp.

**2. Parse and plan**
GPT-4o parses your idea into a structured production spec: which content folder to pull from, duration, style, whether to include voiceover.

**3. Clip scoring**
GPT-4o Vision scores clips in your folder for quality, relevance to the mood, and visual appeal.

**4. Voiceover generation**
If requested, GPT-4o writes a voiceover script and OpenAI TTS (nova voice) generates the audio file.

**5. FFmpeg assembly**
`reel_creator.py` runs:
- Crops each clip to 9:16
- Trims to budget duration per clip
- Applies xfade transitions
- Mixes voiceover over background audio
- Burns captions from the voiceover script

**6. Preview**
The assembled reel is uploaded to Imgur. WhatsApp sends you the preview link and a music suggestion.

**7. Reply**
`POST` -- uploads to Instagram Reels + Threads
`REDO` -- triggers a new assembly with different clip selection
`SKIP` -- discards

---

## Data flow diagram

```
[Content folder] -- new file dropped
       |
       v
[n8n File Trigger]
       |
       v
[Skip output folders?] -- yes --> ignore
       | no
       v
[Get file context]
(folder name -> blur level, vault flag)
       |
   vault_only? -- yes --> [Copy to vault] --> done
       | no
       v
[GPT-4o Vision]
(blur region detection)
       |
       v
[Sharp.js blur] --> [_approved/instagram/]
[Copy original] --> [_vault/OF_ready/]
       |
       v
[GPT-4o captions]
(3 options in persona voice)
       |
       v
[Twilio WhatsApp]
(approval message)
       |
    Y1/Y2/Y3
       |
       v
[Imgur upload] --> public URL
       |
       v
[Instagram Graph API]
[Threads API]
       |
       v
[WhatsApp confirmation]
```

---

## n8n workflow architecture

Each persona has its own completely isolated set of workflows. They share the same n8n server but never interact.

```
n8n (localhost:5678)
│
├── Persona 1 — Image Pipeline
├── Persona 1 — Approval Handler
├── Persona 1 — Reel Creator
│
├── Persona 2 — Image Pipeline    <- same JSON, different config
├── Persona 2 — Approval Handler
│
└── Persona 3 — Image Pipeline
    Persona 3 — Approval Handler
```

Critical rule: each workflow's file watcher path and voice brief are configured separately. They do not share state.

---

## State management

Pending approvals are stored in `pending_approvals.json` in your scripts folder. This is a simple flat JSON file:

```json
{
  "p1_1234567890": {
    "id": "p1_1234567890",
    "fileName": "dance_clip.jpg",
    "captions": ["caption 1", "caption 2", "caption 3"],
    "hashtags": ["#tag1", "#tag2"],
    "instagramPath": "D:\\content_approved\\instagram\\dance_clip_p1_1234567890.jpg",
    "status": "pending"
  }
}
```

When you reply to an approval, the handler looks up the ID and marks the entry as approved or rejected.

---

## API calls and costs

Every image processed makes approximately:
- 1x GPT-4o Vision call (blur detection): ~$0.01-0.03
- 1x GPT-4o call (caption generation): ~$0.005
- 1x Twilio WhatsApp message: ~$0.005
- 1x Imgur upload: free
- 2x platform API calls (IG + Threads): free

**Per image total: roughly $0.02-0.05**

For reels, add:
- GPT-4o Vision clip scoring (scales with number of clips): ~$0.05-0.20
- OpenAI TTS voiceover: ~$0.015 per 1000 characters
