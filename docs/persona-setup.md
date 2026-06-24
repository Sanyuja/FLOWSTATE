# Persona Setup Guide

A persona is your content identity. FLOWSTATE runs each persona as a completely isolated workflow -- different voice, different folders, different platforms, never overlapping.

---

## The persona config file

Start by copying `config/persona.example.json` and editing it. This config does two things:

1. **Documents** what your persona is (for your own reference)
2. **Provides the text you paste** into the n8n workflow nodes (voice brief, folder rules, post times)

---

## The voice brief

This is the most important field. The AI writes every single caption in this voice. Spend time on it.

**Too vague (bad):**
```json
"voice_brief": "Friendly and confident."
```

**Specific enough to be useful (good):**
```json
"voice_brief": "Warm, direct, slightly playful. Never corporate, never hustle-culture. Short punchy captions -- 1-2 sentences max. She states, she invites, she disappears. No exclamation marks. Hashtags go in the first comment, never in the caption body. Audience expects: aesthetic lifestyle, real moments, no performative positivity."
```

Include:
- The tone (adjectives)
- What you never say
- Sentence length and punctuation style
- What your audience expects
- Any platform-specific notes

---

## Content folders

Each subfolder in your content base maps to a blur level and optional vault flag.

```json
"content_folders": {
  "lifestyle":  { "blur": "none"       },
  "coffee":     { "blur": "none"       },
  "fitness":    { "blur": "moderate"   },
  "dance":      { "blur": "aggressive" },
  "private":    { "vault_only": true   }
}
```

**Blur levels:**

| Level | What it does | Use for |
|---|---|---|
| `none` | No blur applied | Fully safe content |
| `light` | Only explicit violations | Mild content, faces, family |
| `moderate` | Midriff, necklines, form-fitting areas | Outfits, activewear |
| `aggressive` | All visible skin, body-revealing poses | Dance, pole, bold content |
| `vault_only` | Copied to vault, never posted | Private or adult content |

Folder names are matched by the parent folder of the dropped file. So a file dropped into `D:\your-content\dance\clip.jpg` maps to the `dance` rule.

---

## Setting up your content folder structure

Create your folders before activating the workflows. Example:

```
D:\your-content\                <- CONTENT_BASE
│
├── lifestyle\
├── coffee\
├── fitness\
├── dance\
└── private\

D:\your-content_approved\       <- APPROVED_BASE
├── instagram\
├── threads\
└── x\

D:\your-content_vault\          <- VAULT_BASE
├── OF_ready\
├── watermarked\
└── reel_review\
```

The `setup.ps1` script creates the `_approved` and `_vault` folders automatically.

---

## Configuring the n8n workflow

After importing `workflows/image_pipeline.json` into n8n, find and update these two nodes (both are marked with `CONFIGURE THIS` in the code):

**Node: Get File Context**
Update the `blurMap` object to match your folder names and blur levels:

```javascript
const blurMap = {
  'lifestyle':  { level: 'none',       needsBlur: false, vaultOnly: false },
  'coffee':     { level: 'none',       needsBlur: false, vaultOnly: false },
  'fitness':    { level: 'moderate',   needsBlur: true,  vaultOnly: false },
  'dance':      { level: 'aggressive', needsBlur: true,  vaultOnly: false },
  'private':    { level: 'none',       needsBlur: false, vaultOnly: true  },
};
```

Also update the output paths in the same node to match your `APPROVED_BASE` and `VAULT_BASE`.

**Node: Generate Captions**
Replace the `content` field in the system message with your voice brief:

```javascript
content: 'YOUR VOICE BRIEF HERE. Return ONLY valid JSON, no markdown.'
```

Also update the `timeMap` to set best posting times for each of your folders.

---

## Multiple personas

To add a second persona:

1. Import the workflow files again in n8n (give them a new name, e.g. `Persona 2 -- Image Pipeline`)
2. Update the file watcher path to your second persona's content folder
3. Update the blurMap and voice brief for the new persona
4. Create a separate `pending_approvals_p2.json` state file (or use a different key prefix)
5. Both workflows share the same Twilio bot -- approvals are tagged by persona in the message

Critical rule: the two workflows must watch completely different folders. They should never touch the same files.

---

## Testing your persona config

Before going live, test with a single safe image:

1. Drop a low-stakes image (e.g. a coffee photo) into your content folder
2. Wait 30-60 seconds
3. Check n8n execution logs for any errors
4. Confirm WhatsApp approval message arrives
5. Read the 3 captions -- do they sound like your voice brief?
6. Reply N to skip (don't post until you're happy with caption quality)

Iterate on the voice brief until the captions feel right.
