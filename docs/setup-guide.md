# FLOWSTATE Setup Guide

Get a working content automation system in an afternoon.

---

## What You'll Need

| Account | Cost | Time to Set Up |
|---|---|---|
| n8n (self-hosted) | Free | 10 min |
| OpenAI | Pay per use (~$5/month) | 5 min |
| Twilio (WhatsApp) | Free trial credit | 15 min |
| ngrok | Free tier | 5 min |
| Platform APIs (Instagram, LinkedIn, etc.) | Free | 20 min each |

**Total:** About 2–3 hours first-time. 10 minutes/week after that.

---

## Step 1 — Install n8n

n8n is the automation brain. It runs locally on your machine (Windows, Mac, or Linux).

```bash
npm install -g n8n
n8n start
```

Open [http://localhost:5678](http://localhost:5678) — you'll see the n8n editor.

> If you want n8n to survive restarts, install PM2:
> ```bash
> npm install -g pm2
> pm2 start n8n -- start
> pm2 startup
> pm2 save
> ```

---

## Step 2 — Set Up Your Environment

```bash
git clone https://github.com/sanyuja/flowstate
cd flowstate
cp .env.example .env
```

Open `.env` and fill in your API keys. See sections below for how to get each one.

---

## Step 3 — Get Your API Keys

### OpenAI (for caption generation)
1. Go to [platform.openai.com](https://platform.openai.com)
2. API Keys → Create new secret key
3. Paste into `.env` as `OPENAI_API_KEY`

### Twilio (for WhatsApp approval)
1. Sign up at [twilio.com](https://twilio.com) — free trial gives you $15 credit
2. Console → Account SID + Auth Token → paste into `.env`
3. Messaging → Try it out → Send a WhatsApp message → follow the sandbox setup
4. Your personal WhatsApp number becomes `TWILIO_WHATSAPP_TO`

### ngrok (exposes your local n8n to Twilio)
1. Download from [ngrok.com](https://ngrok.com) — free tier
2. ```bash
   ngrok http 5678
   ```
3. Copy the `https://...ngrok.io` URL into `.env` as `NGROK_URL`
4. Note: This URL changes every time you restart ngrok (unless you use a paid static domain)

### Instagram / LinkedIn / Medium
See platform-specific instructions in the [credentials setup guide](./credentials-guide.md) (coming soon — each platform takes about 20 minutes).

---

## Step 4 — Import the Reference Workflow

1. Open n8n at [http://localhost:5678](http://localhost:5678)
2. Click the **+** to create a new workflow
3. Top-right menu → **Import from File**
4. Select `workflows/reference-workflow.json`
5. The workflow loads — you'll see nodes that need configuring

---

## Step 5 — Build Your Persona Config (stays local, never committed)

Create a file called `persona.json` in the root folder. It's in `.gitignore` — it never touches GitHub.

```json
{
  "handle": "your-public-handle",
  "display_name": "Your Name",
  "voice_brief": "Write in warm, direct, first-person voice. Short sentences. No buzzwords. Sound like a smart friend, not a brand.",
  "platforms": ["linkedin", "instagram"],
  "content_rules": {
    "never_post": ["politics", "religion"],
    "always_include": ["personal angle", "one concrete takeaway"]
  }
}
```

Reference this file in your n8n workflow nodes — never hardcode personal info in the workflow itself.

---

## Step 6 — Adapt the Prompts

Open `/prompts/` and find the caption writer prompt. Update the voice section to match your `persona.json`. Run a test with one image before you go live.

---

## Step 7 — Test Before Going Live

1. Drop a test image into your watched folder
2. Check n8n — the workflow should trigger
3. You should receive a WhatsApp message with the preview
4. Reply `Y1` — confirm it posts correctly
5. If something breaks, check the n8n execution log for the error

---

## What to Do Each Week

**Your entire job:**
1. Drop content into the correct folder
2. Reply to WhatsApp previews
3. Read the Sunday digest

That's it. Everything else is automated.

---

## Troubleshooting

**n8n doesn't trigger when I drop a file**
Check that the folder path in the File Trigger node matches your actual content folder.

**WhatsApp message doesn't arrive**
Check your ngrok URL is correct in Twilio's webhook settings. Ngrok URL changes on restart — update it in Twilio after each restart.

**Captions don't sound like me**
Update your `voice_brief` in `persona.json` and re-run. The more specific the voice brief, the better.

**Instagram token expired**
Instagram tokens last 60 days. Set a calendar reminder at day 50 to refresh. See the credentials guide for the refresh command.
