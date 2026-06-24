# FLOWSTATE

> Drop a file. Get a WhatsApp ping. Tap approve. It's live.

FLOWSTATE is a self-hosted AI content automation system. You define your personas, drop content into folders, and the system handles everything else — AI image analysis, auto-blur, caption writing, platform posting, and AI reel assembly.

No apps to open. No captions to write. No scheduling.

**Built and tested by [Sanyuja Desai](https://www.linkedin.com/in/sanyujadesai) across 3 distinct content personas.**

---

## How it works

```
You drop a file into your persona's content folder
         ↓
n8n detects it automatically (folder watcher)
         ↓
GPT-4o Vision analyses the image — type, category, safety check
         ↓
Your persona's rules apply — blur sensitive regions, route to vault, or pass
         ↓
GPT-4o writes 3 caption options in your persona's voice
         ↓
WhatsApp sends you a preview + the 3 captions
         ↓
You reply Y1 / Y2 / Y3 (approve) or N (skip)  ← takes 10 seconds
         ↓
Content posts to all platforms for that persona
```

**For reels:** Send `IDEA: [your concept]` via WhatsApp → AI scores your clips, generates a voiceover, assembles via FFmpeg, burns captions → sends you a preview link → you reply POST or SKIP.

---

## What you never have to do again

- Write captions
- Schedule posts
- Resize or reformat content
- Cross-post between platforms
- Edit reels (crop to 9:16, transitions, voiceover, captions)
- Think about hashtags
- Open Instagram to post manually

---

## Tech stack

| Layer | Tool | Cost |
|---|---|---|
| Automation brain | n8n (self-hosted) | Free |
| AI vision + captions | GPT-4o | ~$0.01-0.05/image |
| AI voiceover | OpenAI TTS | ~$0.015/1k chars |
| Image processing | Sharp.js | Free |
| Video assembly | FFmpeg + Python | Free |
| Image hosting | Imgur API | Free |
| Post to Instagram | Instagram Graph API | Free |
| Post to Threads | Threads API | Free |
| WhatsApp approval bot | Twilio | ~$0.005/message |
| Webhook tunnel | ngrok | Free tier |

**Total running cost: roughly $5-20/month** depending on how much content you push through.

---

## Repo structure

```
flowstate/
├── workflows/                         <- Import these three files into n8n
│   ├── image_pipeline.json            <- Folder watcher -> blur -> captions -> WhatsApp
│   ├── approval_handler.json          <- Receives your reply -> posts to platforms
│   └── reel_creator.json             <- WhatsApp IDEA -> assembles reel -> preview
│
├── scripts/                           <- Deployed to your content scripts folder
│   ├── blur.js                        <- Node.js: GPT-4o Vision + Sharp blur
│   └── reel_creator.py               <- Python: FFmpeg reel assembly pipeline
│
├── config/
│   └── persona.example.json           <- Your persona definition -- start here
│
├── setup/
│   ├── setup.ps1                      <- One-time Windows setup (run as Admin)
│   └── install_reel_deps.ps1         <- Install FFmpeg + Python deps
│
├── docs/
│   ├── how-it-works.md               <- Full system architecture
│   ├── persona-setup.md              <- Configuring your persona and folders
│   ├── credentials-setup.md          <- Getting every API key, step by step
│   └── reel-creator.md              <- Using the reel creator
│
├── .env.example                       <- All environment variables you need
├── requirements.txt                   <- Python dependencies
└── CONTRIBUTING.md
```

---

## Persona configuration

FLOWSTATE runs on the concept of **personas** -- distinct content identities with their own voice, platforms, and content rules. One person can run multiple personas completely isolated from each other. They do not cross-pollinate.

```json
{
  "persona": {
    "name": "your_handle",
    "display_name": "Your Display Name",
    "voice_brief": "Write your tone here in detail. The AI writes every caption in this voice. Be specific -- mention what you sound like, what you avoid, what your audience expects."
  },
  "platforms": {
    "instagram": true,
    "threads": true,
    "x_manual": true
  },
  "content_folders": {
    "dance":     { "blur": "aggressive" },
    "fits":      { "blur": "moderate"  },
    "lifestyle": { "blur": "light"     },
    "coffee":    { "blur": "none"      },
    "nsfw":      { "vault_only": true  }
  },
  "caption_style": {
    "hashtags_in_first_comment": true,
    "hashtags_per_post": 7,
    "suggested_post_times": {
      "dance":     "8:00 PM",
      "lifestyle": "12:00 PM",
      "coffee":    "9:00 AM"
    }
  }
}
```

See [config/persona.example.json](config/persona.example.json) for the full annotated template.

---

## Quick start

### Prerequisites

- Windows PC (always-on preferred)
- Node.js 20+
- Python 3.10+
- n8n: `npm install -g n8n`
- PM2: `npm install -g pm2`

### 1. Run the setup script

```powershell
# Run PowerShell as Administrator
cd flowstate
.\setup\setup.ps1
.\setup\install_reel_deps.ps1
```

This creates your folder structure, installs Sharp.js, and deploys the scripts.

### 2. Set your credentials

Copy `.env.example` and follow [docs/credentials-setup.md](docs/credentials-setup.md) to get each API key.

Then set them as Windows Machine environment variables and restart n8n:

```powershell
[System.Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "sk-...", "Machine")
[System.Environment]::SetEnvironmentVariable("TWILIO_ACCOUNT_SID", "AC...", "Machine")
# ... full list in docs/credentials-setup.md
pm2 restart n8n
```

### 3. Configure your persona

Copy `config/persona.example.json`, edit the voice brief, folders, and platforms for your use case. See [docs/persona-setup.md](docs/persona-setup.md).

### 4. Import n8n workflows

1. Start n8n: `pm2 start n8n`
2. Open `http://localhost:5678`
3. Import `workflows/image_pipeline.json`
4. Import `workflows/approval_handler.json`
5. Import `workflows/reel_creator.json` (optional -- for reel creation)
6. In each workflow, update the **content folder path** and **voice brief** (marked with `CONFIGURE THIS` comments)
7. Activate all workflows

### 5. Test it

Drop an image into your content folder. Wait about 30 seconds. A WhatsApp approval message should arrive.

---

## Multiple personas

To run a second persona, import the workflow files again into n8n as a separate workflow set. Each persona gets its own:

- Content folder
- n8n workflow (isolated, never interacts with other personas)
- Voice brief
- Platform targets
- Folder-to-blur-level rules

They share the same n8n server, same Twilio bot, same API keys -- completely independent logic.

---

## Reel creator

Send this via WhatsApp:

```
IDEA: [content type], [mood], [duration]s [VO or no VO]
```

Examples:
- `IDEA: dance, moody red light, 20s VO`
- `IDEA: lifestyle, golden hour, 30s no VO`
- `IDEA: fitness, energetic, 15s VO`

The system will:
1. Score clips in your folder using GPT-4o Vision
2. Select the best clips for the described mood
3. Generate a voiceover script (if requested) via OpenAI TTS
4. Assemble via FFmpeg -- 9:16 crop, xfade transitions, voiceover mix, caption burn-in
5. Upload to Imgur, send you a preview link
6. You reply `POST`, `REDO`, or `SKIP`

Available styles: `smooth` · `energetic` · `slow_burn` · `dramatic`

See [docs/reel-creator.md](docs/reel-creator.md) for the full guide.

---

## A real example

FLOWSTATE is what I built for my own content operation. Three completely separate personas running off one system on a home Windows PC:

| Persona | Platforms | Content type |
|---|---|---|
| Personal lifestyle | Instagram | Coffee, home, everyday life |
| Bold lifestyle / pole dance | Instagram + Threads | Fitness, aesthetic, sensual lifestyle |
| VR gaming | Twitch + Instagram + YouTube | Gaming clips, stream highlights |

Each is completely isolated -- different voice, different rules, different platforms. The system handles all caption writing, posting, and reel creation. I have not written a caption manually or opened Instagram to post since setting this up.

---

## Known limitations

**X/Twitter:** The write API costs $100/month minimum. For now, when you approve a post, the WhatsApp confirmation includes the caption so you can paste it into X manually.

**ngrok:** Free tier URLs reset on restart. Sign up for a free ngrok account to get one persistent static domain.

**Instagram + Threads tokens:** Expire every 60 days. Set a recurring calendar reminder at day 50 to refresh. Commands are in [docs/credentials-setup.md](docs/credentials-setup.md).

**Windows only (currently):** Setup scripts are Windows-native. n8n itself runs anywhere -- Linux/Mac users can adapt the folder paths and skip the `.ps1` scripts.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The most useful contributions are persona config examples for different creator types -- fitness, gaming, lifestyle, business, etc.

---

## About

Built by [Sanyuja Desai](https://www.linkedin.com/in/sanyujadesai) -- AI consultant and automation builder.

I built this because I was drowning in the admin of being a multi-platform creator. The system now runs my entire content operation in the background.

- LinkedIn: [sanyujadesai](https://www.linkedin.com/in/sanyujadesai)
- Medium: [@sanyujadesai](https://medium.com/@sanyujadesai)

---

## License

MIT -- free to use, remix, and build on.
