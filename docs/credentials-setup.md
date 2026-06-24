# Credentials Setup Guide

**Total monthly cost: ~$0 fixed + pay-per-use AI calls**

---

## What you need (one-time setup)

| Service | What it does | Cost |
|---|---|---|
| OpenAI | GPT-4o Vision + captions + TTS voiceover | Pay per use (~$0.02-0.05/image) |
| Imgur | Hosts images/videos so Instagram/Threads can access them | Free |
| Instagram Graph API | Posts directly to Instagram | Free |
| Threads API | Posts directly to Threads | Free |
| Twilio | WhatsApp approval messages | Free trial ($15 credit, then ~$0.005/msg) |
| ngrok | Exposes local n8n webhook to Twilio | Free tier |

---

## Step 1 -- OpenAI API key (5 min)

1. Go to [platform.openai.com](https://platform.openai.com) -> API keys -> Create new secret key
2. Copy the key (starts with `sk-`)

```
OPENAI_API_KEY = sk-...
```

---

## Step 2 -- Imgur client ID (5 min)

1. Go to [imgur.com/register](https://imgur.com/register) and create a free account
2. Go to [api.imgur.com/oauth2/addclient](https://api.imgur.com/oauth2/addclient)
3. Fill in:
   - Application name: `flowstate-pipeline`
   - Authorization type: **Anonymous usage without user authorization**
   - Email: your email
4. Click Submit
5. Copy the **Client ID**

```
IMGUR_CLIENT_ID = a1b2c3d4e5f6789
```

---

## Step 3 -- Facebook Developer App (20 min)

This one app gives you both Instagram and Threads access.

### 3a. Create the app

1. Go to [developers.facebook.com](https://developers.facebook.com) -> Log in with Facebook
2. Click **My Apps -> Create App**
3. Choose **Other** -> **Business** -> Next
4. Name it `flowstate-automation` -> Create
5. Note your **App ID** and **App Secret** from the dashboard

### 3b. Instagram Graph API

1. Inside your app -> **Add a Product** -> **Instagram Graph API** -> Set Up
2. Left sidebar -> **Instagram -> API setup with Instagram Login**
3. Click **Generate Token** -> log in with your Instagram account

   > Your Instagram must be a **Professional account** (Creator or Business). Switch in: Instagram app -> Settings -> Account -> Switch to Professional Account. It's free.

4. Copy the short-lived token (expires in 1 hour -- exchange it next)

### 3c. Get a long-lived Instagram token (lasts 60 days)

Paste this URL into your browser (replace the values):

```
https://graph.facebook.com/v18.0/oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id=YOUR_APP_ID
  &client_secret=YOUR_APP_SECRET
  &fb_exchange_token=YOUR_SHORT_LIVED_TOKEN
```

Copy the `access_token` from the JSON response.

### 3d. Get your Instagram User ID

```
https://graph.facebook.com/v18.0/me?fields=id,name&access_token=YOUR_LONG_LIVED_TOKEN
```

Copy the `id` field.

```
INSTAGRAM_USER_ID     = 123456789012345
INSTAGRAM_ACCESS_TOKEN = EAAxxxx...
```

> Set a recurring calendar reminder at **day 50** to refresh your token. Refresh command:
> `https://graph.facebook.com/v18.0/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=CURRENT_TOKEN`

---

## Step 4 -- Threads API (10 min)

Uses the same Facebook Developer app you just created.

### 4a. Add Threads API

1. In your app -> **Add a Product** -> **Threads API** -> Set Up
2. Under **Threads -> API Setup** -> **Generate Token**
3. Log in with your Threads/Instagram account
4. Approve: `threads_basic`, `threads_content_publish`

### 4b. Get long-lived Threads token

```
https://graph.threads.net/access_token
  ?grant_type=th_exchange_token
  &client_id=YOUR_APP_ID
  &client_secret=YOUR_APP_SECRET
  &access_token=YOUR_SHORT_LIVED_THREADS_TOKEN
```

### 4c. Get your Threads User ID

```
https://graph.threads.net/v1.0/me?fields=id,name&access_token=YOUR_THREADS_TOKEN
```

```
THREADS_USER_ID     = 987654321098765
THREADS_ACCESS_TOKEN = THBxxxx...
```

> Same 60-day expiry. Set your reminder at day 50. Refresh command:
> `https://graph.threads.net/access_token?grant_type=th_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&access_token=CURRENT_TOKEN`

---

## Step 5 -- Twilio WhatsApp sandbox (10 min)

1. Go to [twilio.com](https://twilio.com) -> Sign up (free, $15 trial credit)
2. From the Console, copy your:
   - **Account SID** (starts with `AC`)
   - **Auth Token** (click to reveal)
3. Go to **Messaging -> Try it Out -> Send a WhatsApp Message**
4. Follow the instructions: send the join code from your WhatsApp to `+14155238886`
5. Your WhatsApp is now connected to the sandbox

```
TWILIO_ACCOUNT_SID   = ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN    = your_auth_token
TWILIO_WHATSAPP_FROM = whatsapp:+14155238886
TWILIO_WHATSAPP_TO   = whatsapp:+1XXXXXXXXXX  <- your number
```

---

## Step 6 -- ngrok (5 min)

ngrok creates a public HTTPS URL so Twilio can send WhatsApp replies back to your local n8n.

```powershell
npm install -g ngrok
ngrok http 5678
```

You'll see something like:

```
Forwarding  https://abc123.ngrok-free.app -> http://localhost:5678
```

Copy that HTTPS URL. Then in Twilio:

1. Console -> **Messaging -> Settings -> WhatsApp Sandbox Settings**
2. **When a message comes in:** `https://abc123.ngrok-free.app/webhook/approval-handler`
3. Method: **HTTP POST** -> Save

```
N8N_WEBHOOK_URL = https://abc123.ngrok-free.app
```

> Free ngrok URLs reset every time you restart ngrok. Create a free account at [ngrok.com](https://ngrok.com) to get one persistent static domain. When the URL changes, update `N8N_WEBHOOK_URL` and the Twilio webhook setting.

---

## Step 7 -- Set all env vars in PowerShell

Run as Administrator:

```powershell
[System.Environment]::SetEnvironmentVariable("OPENAI_API_KEY",          "sk-...",                    "Machine")
[System.Environment]::SetEnvironmentVariable("IMGUR_CLIENT_ID",         "a1b2c3d4e5f6789",           "Machine")
[System.Environment]::SetEnvironmentVariable("INSTAGRAM_USER_ID",       "123456789012345",            "Machine")
[System.Environment]::SetEnvironmentVariable("INSTAGRAM_ACCESS_TOKEN",  "EAAxxxxxxxxxxxxxxxxxx",      "Machine")
[System.Environment]::SetEnvironmentVariable("THREADS_USER_ID",         "987654321098765",            "Machine")
[System.Environment]::SetEnvironmentVariable("THREADS_ACCESS_TOKEN",    "THBxxxxxxxxxxxxxxxxxx",      "Machine")
[System.Environment]::SetEnvironmentVariable("TWILIO_ACCOUNT_SID",      "ACxxxxxxxxxxxxxxxxxxxxxxxx", "Machine")
[System.Environment]::SetEnvironmentVariable("TWILIO_AUTH_TOKEN",       "your_auth_token",            "Machine")
[System.Environment]::SetEnvironmentVariable("TWILIO_WHATSAPP_FROM",    "whatsapp:+14155238886",      "Machine")
[System.Environment]::SetEnvironmentVariable("TWILIO_WHATSAPP_TO",      "whatsapp:+1XXXXXXXXXX",      "Machine")
[System.Environment]::SetEnvironmentVariable("N8N_WEBHOOK_URL",         "https://xxxx.ngrok-free.app","Machine")
[System.Environment]::SetEnvironmentVariable("CONTENT_BASE",            "D:\your-content-folder",     "Machine")
[System.Environment]::SetEnvironmentVariable("APPROVED_BASE",           "D:\your-content-folder_approved","Machine")
[System.Environment]::SetEnvironmentVariable("VAULT_BASE",              "D:\your-content-folder_vault","Machine")
[System.Environment]::SetEnvironmentVariable("SCRIPTS_DIR",             "D:\your-content-folder\scripts","Machine")

pm2 restart n8n
```

---

## About X/Twitter

The official X API requires the **Basic tier** ($100/month) for write access. There is no free posting option.

For now: when you approve a post, the WhatsApp confirmation includes the full caption text so you can paste it into X manually. If X automation becomes important, a browser automation approach can be added later.

---

## Token refresh reminder

Instagram and Threads long-lived tokens expire after 60 days. Set a recurring calendar event at day 50.

**Instagram refresh:**
```
https://graph.facebook.com/v18.0/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=CURRENT_TOKEN
```

**Threads refresh:**
```
https://graph.threads.net/access_token?grant_type=th_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&access_token=CURRENT_TOKEN
```

After refreshing, update the env vars and restart n8n:
```powershell
[System.Environment]::SetEnvironmentVariable("INSTAGRAM_ACCESS_TOKEN", "new_token", "Machine")
[System.Environment]::SetEnvironmentVariable("THREADS_ACCESS_TOKEN",   "new_token", "Machine")
pm2 restart n8n
```
