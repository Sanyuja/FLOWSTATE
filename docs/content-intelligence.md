# Content Intelligence Guide

This layer runs before the main approval pipeline. It organizes your raw content library, builds a queryable database, and sends you a daily WhatsApp nudge with trend-matched post suggestions.

---

## The full pipeline

```
raw content folder
       ↓
content_tagger.py       ← CLIP ViT-L-14 auto-tags every file
       ↓
content_refiner.py      ← Claude Haiku Vision enriches hero images + writes captions
       ↓
content_organizer.py    ← moves files from raw to categorized folders
       ↓
content_db_updater.py   ← builds master_content_db.xlsx + content_inventory.json
       ↓
n8n: Trend Scout        ← daily 9am: trends + inventory → WhatsApp nudge
       ↓
you reply Y1/Y2/Y3      ← existing approval_handler posts it
```

---

## Step 1 — content_tagger.py

Scans your entire content folder and classifies every image and video using OpenCLIP (ViT-L-14 LAION weights). No API calls — runs locally on GPU if available, CPU otherwise.

**What it detects per file:**
- `vibe` — overall aesthetic feel
- `outfit` — what's being worn
- `pose` — body position
- `activity` — what's happening
- `location` — where it is
- `lighting` — lighting type
- `style` — content aesthetic
- `platform_fit` — safe-for-work or adult
- `face_detected` — YES/blank

**Run:**
```powershell
cd "your-project-folder"
python scripts/content_tagger.py
```

First run downloads the ViT-L-14 model (~800MB). Uses checkpointing — safe to interrupt and resume.

**Customizing CLIP prompts:**
The prompts in `content_tagger.py` under `PROMPTS` define what gets detected. Edit them to match your actual content categories. The prompts are just plain English descriptions — the model scores every file against all of them and picks the best match per category.

---

## Step 2 — content_refiner.py

Takes the CLIP output and runs Claude Haiku Vision on your top 5 images per category. Produces richer, more accurate labels and ready-to-post captions per platform.

**Requires:**
- `ANTHROPIC_API_KEY` env var
- `PERSONA_VOICE_BRIEF` env var (or set `voice_brief` in `config/persona.json`)

**Cost:** ~$0.003-0.008 per image (Haiku pricing). For 50 hero images ≈ $0.15-0.40 total.

**Run:**
```powershell
python scripts/content_refiner.py
```

Outputs:
- `CONTENT_BASE/claude_refined_output.csv` — enriched labels
- `CONTENT_BASE/captions_output.csv` — per-platform captions

---

## Step 3 — content_organizer.py

Reads the CLIP tags and moves files from raw/import folders into categorized subfolders based on rules you define.

**Always run --dry-run first:**
```powershell
python scripts/content_organizer.py --dry-run
# review the output, then:
python scripts/content_organizer.py
```

**Configuring routing rules:**
Edit the `RULES` list in `content_organizer.py`. Each rule is:
```python
("field", ["keyword1", "keyword2"], "target_folder")
```

Priority order matters — first match wins. Sensitive content routes to `_VAULT` automatically.

**Raw source folders:**
Edit `RAW_ROOTS` in the script to match where your content lands (phone uploads, camera roll imports, etc.).

---

## Step 4 — content_db_updater.py

Merges all outputs into `master_content_db.xlsx` and exports `content_inventory.json` for the n8n Trend Scout.

**Run:**
```powershell
python scripts/content_db_updater.py
```

**Outputs:**
- `SCRIPTS_DIR/master_content_db.xlsx` — Dashboard + Master DB + Platform Routing + Captions sheets
- `SCRIPTS_DIR/content_inventory.json` — lightweight JSON for n8n to query

**Run this after every batch of new content** so the Trend Scout has an up-to-date inventory to pick from.

---

## Step 5 — n8n Trend Scout workflow

Import `workflows/trend_scout.json` into n8n. This workflow runs at 9am daily and:

1. Reads `content_inventory.json`
2. Calls GPT-4o to research trending hashtags and themes for your niches
3. Scores your unposted content against the trends (keyword match on vibe/activity/style)
4. Calls GPT-4o to generate 3 trend-aware captions for the best match
5. Saves the item to `pending_approvals.json` (same format as the image pipeline)
6. Sends you a WhatsApp message

**What you receive:**
```
📈 Trending today: #quietluxury #slowliving #morningroutine
Trending concept: slow aesthetic morning with minimal setup
Best time to post: 7-9pm EST

Best match: coffee/IMG_0234.jpg

Y1: "morning ritual."
Y2: "the quiet before everything."
Y3: "soft start."

Reply Y1/Y2/Y3 to post. N to skip.

Or send: IDEA: slow aesthetic morning, 20s VO
```

Replying Y1/Y2/Y3 routes through the existing `approval_handler` workflow — no extra setup needed.

**Configure before activating:**

In the `📡 Scout, Caption, Save & Send` Code node, find and update:

```javascript
// CONFIGURE THIS: your content niches
const PERSONA_NICHES = process.env.PERSONA_NICHES || 'lifestyle, fashion, fitness';
```

Set `PERSONA_NICHES` as a Machine env var:
```powershell
[System.Environment]::SetEnvironmentVariable("PERSONA_NICHES", "lifestyle, fitness, dance", "Machine")
pm2 restart n8n
```

Also update the caption system prompt in the Code node to use your persona voice brief.

---

## Scheduling the Python scripts

Run the 4 Python scripts once per week (or after a big content drop). You can automate this with Windows Task Scheduler or a PowerShell script:

```powershell
# run_content_pipeline.ps1
cd "your-project-folder"
python scripts/content_tagger.py
python scripts/content_refiner.py
python scripts/content_organizer.py --dry-run   # remove --dry-run once you trust the rules
python scripts/content_db_updater.py
Write-Host "Content pipeline complete."
```

---

## Additional dependencies

The content tagger requires PyTorch and OpenCLIP — heavier than the base requirements:

```powershell
pip install open_clip_torch torch torchvision mediapipe opencv-python
```

GPU acceleration (optional but 10-50x faster for large libraries):
- Install CUDA Toolkit 12.x from nvidia.com
- Install the CUDA-enabled PyTorch: `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121`

CPU-only works fine for libraries under ~500 files.

---

## Costs

| Step | Cost |
|---|---|
| content_tagger.py | Free (local CLIP model) |
| content_refiner.py | ~$0.003-0.008/image (Claude Haiku) |
| Trend Scout: trend research | ~$0.01/day (GPT-4o) |
| Trend Scout: caption generation | ~$0.01/day (GPT-4o) |
| **Total per month** | **~$1-3 for active pipeline** |

---

## Upgrading trend research

The default Trend Scout uses GPT-4o's training knowledge for trend suggestions, which is directionally accurate but not real-time. To get actual live trending hashtags, replace the trend research call with:

**Option A — Perplexity API** (web search, ~$0.02/call):
```javascript
const resp = await fetch('https://api.perplexity.ai/chat/completions', {
  method: 'POST',
  headers: { 'Authorization': 'Bearer ' + process.env.PERPLEXITY_API_KEY, 'Content-Type': 'application/json' },
  body: JSON.stringify({
    model: 'llama-3.1-sonar-small-128k-online',
    messages: [{ role: 'user', content: `What are trending Instagram hashtags for ${PERSONA_NICHES} right now? Return JSON: {"hashtags": [...10]}` }]
  })
});
```

**Option B — RapidAPI Instagram hashtag endpoint** (free tier available):
Search RapidAPI for "Instagram hashtag" — several endpoints return trending tags by keyword with free tier credits.
