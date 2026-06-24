# Docker Setup Guide

Run FLOWSTATE with a single command on any OS. No Node.js, no Python, no n8n installed globally — Docker handles everything.

```bash
docker compose up -d
```

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Mac, Windows, Linux)
- A [Twilio account](https://twilio.com) and WhatsApp sandbox number
- Your API keys (OpenAI, Anthropic, Instagram, Threads)
- An [ngrok account](https://ngrok.com) (free tier works)

---

## Step 1 — Clone and configure

```bash
git clone https://github.com/Sanyuja/FLOWSTATE
cd FLOWSTATE
cp .env.example .env
```

Open `.env` and fill in:

```bash
# API keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
IMGUR_CLIENT_ID=...

# Instagram + Threads
INSTAGRAM_USER_ID=...
INSTAGRAM_ACCESS_TOKEN=EAAxxxx...
THREADS_USER_ID=...
THREADS_ACCESS_TOKEN=THBxxxx...

# Twilio
TWILIO_ACCOUNT_SID=ACxxxx...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TWILIO_WHATSAPP_TO=whatsapp:+1XXXXXXXXXX

# ngrok
NGROK_AUTHTOKEN=...

# Your content folder — absolute path on your HOST machine
# Mac/Linux:  CONTENT_PATH=/Users/yourname/content
# Windows:    CONTENT_PATH=C:/Users/yourname/content
CONTENT_PATH=/path/to/your/content

# n8n encryption key — generate once, keep it safe:
# Mac/Linux:  openssl rand -hex 32
# Windows:    -join ((1..32) | ForEach-Object { '{0:x2}' -f (Get-Random -Max 256) })
N8N_ENCRYPTION_KEY=your-32-byte-hex-key

# Trend Scout niches
PERSONA_NICHES=lifestyle, fashion, fitness
```

---

## Step 2 — Start n8n

```bash
docker compose up -d
```

First run builds the image (installs Python, FFmpeg, Sharp) — takes 3–5 minutes. Subsequent starts are instant.

Open n8n at **http://localhost:5678** and complete account setup.

---

## Step 3 — Get a public URL (ngrok)

Twilio needs a public HTTPS URL to send webhook events to your n8n. Start ngrok alongside n8n:

```bash
docker compose --profile ngrok up -d
```

Get your public URL:

```bash
docker compose logs ngrok | grep "url="
```

Copy the `https://xxxx.ngrok-free.app` URL. Then:

1. Update `WEBHOOK_URL` in `.env`:
   ```
   WEBHOOK_URL=https://xxxx.ngrok-free.app
   ```
2. Restart n8n to apply:
   ```bash
   docker compose restart n8n
   ```
3. In Twilio console → WhatsApp sandbox → configure the webhook URL:
   ```
   https://xxxx.ngrok-free.app/webhook/approval-handler
   ```

**Tip:** Sign up for a free ngrok account to get a static domain — then your URL never changes on restart.

---

## Step 4 — Import n8n workflows

In n8n at http://localhost:5678:

1. Go to **Workflows** → **Import**
2. Import all four files from `workflows/`:
   - `image_pipeline.json`
   - `approval_handler.json`
   - `reel_creator.json` (optional)
   - `trend_scout.json` (optional)
   - `token_refresh.json` (recommended)
3. In each workflow, find nodes marked `CONFIGURE THIS` and update:
   - `image_pipeline.json` → voice brief in the Generate Captions node
   - `trend_scout.json` → `PERSONA_NICHES` is already read from env var
4. Activate all workflows

---

## Step 5 — Test it

Drop an image into the folder you set as `CONTENT_PATH`. Wait ~30 seconds. A WhatsApp approval message should arrive.

---

## Running the content pipeline (content_tagger.py etc.)

The Python content intelligence scripts run on your **host machine**, not inside Docker — they need GPU access for the CLIP model.

```bash
# From the FLOWSTATE directory, with Python and deps installed on your host:
CONTENT_BASE=/path/to/your/content python scripts/content_tagger.py
CONTENT_BASE=/path/to/your/content python scripts/content_refiner.py
CONTENT_BASE=/path/to/your/content python scripts/content_organizer.py --dry-run
SCRIPTS_DIR=./data python scripts/content_db_updater.py
```

The `content_inventory.json` written to `./data/` is automatically available inside the n8n container at `/data/scripts/content_inventory.json`.

See [content-intelligence.md](content-intelligence.md) for the full content pipeline guide.

---

## Token auto-refresh

Import `workflows/token_refresh.json`. It runs on the 1st of each month at 10am and:

1. Calls Meta's token refresh API for both Instagram and Threads
2. Saves the new tokens to `data/tokens.json`
3. Sends you a WhatsApp confirmation

**No restart needed.** The approval workflow reads `tokens.json` on every run, so new tokens take effect immediately. The 60-day expiry clock resets automatically.

---

## Useful commands

```bash
# Start everything
docker compose up -d

# Start with ngrok
docker compose --profile ngrok up -d

# View n8n logs
docker compose logs -f n8n

# Stop everything
docker compose down

# Restart n8n (e.g. after .env changes)
docker compose restart n8n

# Update to latest FLOWSTATE + rebuild image
git pull
docker compose build --no-cache
docker compose up -d

# Backup n8n database (workflows, credentials)
docker run --rm -v flowstate-n8n-data:/data alpine tar czf - /data > n8n-backup.tar.gz

# Restore
docker run --rm -i -v flowstate-n8n-data:/data alpine tar xzf - < n8n-backup.tar.gz
```

---

## Multiple personas (Docker)

Each persona gets its own `docker-compose.yml` with a different `CONTENT_PATH` and a different n8n port. They share the same host machine but run completely isolated.

Example second persona on port 5679:

```yaml
# docker-compose.persona2.yml
services:
  n8n-persona2:
    build: .
    ports: ["5679:5678"]
    volumes:
      - n8n_persona2:/home/node/.n8n
      - /path/to/persona2/content:/data/content
      - ./persona2-data:/data/scripts
      - ./scripts:/data/src:ro
    env_file: .env.persona2
    environment:
      N8N_PORT: "5678"
      CONTENT_BASE: "/data/content"
      SCRIPTS_DIR: "/data/scripts"

volumes:
  n8n_persona2:
```

```bash
docker compose -f docker-compose.persona2.yml up -d
```

---

## Troubleshooting

**n8n won't start:**
Check logs: `docker compose logs n8n`. Most common: `N8N_ENCRYPTION_KEY` not set.

**Sharp not found in Code nodes:**
Ensure `NODE_PATH=/home/node/n8n-modules/node_modules` and `NODE_FUNCTION_ALLOW_EXTERNAL=sharp` are in the environment (they're in `docker-compose.yml` by default).

**Twilio webhook not arriving:**
Make sure ngrok is running and `WEBHOOK_URL` in `.env` matches the current ngrok URL. After updating `WEBHOOK_URL`, run `docker compose restart n8n`.

**Content path not found:**
`CONTENT_PATH` must be an absolute path on the host. Verify with: `docker compose exec n8n ls /data/content`

**Token refresh failing:**
Check n8n logs for `[TokenRefresh]` lines. The most common cause is a token that already expired — refresh it manually once via the Meta developer console, update `.env`, and the auto-refresh will handle all future renewals.
