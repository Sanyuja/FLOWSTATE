# Persona Guide — Keeping Your Worlds Separate

One of FLOWSTATE's core principles: **your configuration is not your code.**

Your code (workflows, scripts, prompts) lives on GitHub. Your configuration (your name, your handles, your voice, your content rules) lives on your machine, in files that are explicitly excluded from the repo.

This isn't just good security. It's what lets FLOWSTATE be a product others can use — they bring their own configuration to the same framework.

---

## The Separation Rule

| Lives in the repo (public) | Lives on your machine (private) |
|---|---|
| Workflow structure | Your API keys (.env) |
| Prompt templates | Your persona.json |
| Setup guide | Your actual n8n workflow exports |
| Reference workflow (no credentials) | Your content folders and media |

If it contains your name, your handle, your email, your phone number, or your account IDs — it stays local.

---

## If You Have Multiple Personas

FLOWSTATE supports multiple completely isolated personas. Each persona gets:
- Its own folder to watch
- Its own voice brief
- Its own platform targets
- Its own content rules
- Its own WhatsApp approval flow

They never cross-pollinate. The system treats them as different people.

### File structure for multiple personas

```
persona-1.json      ← gitignored
persona-2.json      ← gitignored
persona-3.json      ← gitignored
```

In your n8n workflow, the file path determines which persona config loads. Content dropped into `/persona-1-folder/` uses `persona-1.json`. Content dropped into `/persona-2-folder/` uses `persona-2.json`.

They share the same automation engine. They share nothing else.

---

## Persona Config Schema

```json
{
  "id": "persona-1",
  "display_name": "Your Name or Handle",
  "voice_brief": "Your detailed voice description. The more specific, the better the captions.",
  "platforms": ["linkedin", "instagram", "threads"],
  "posting_rules": {
    "max_per_week": 5,
    "best_times": ["9am", "6pm"],
    "never_post_on": ["sunday"]
  },
  "content_rules": {
    "safe_for_all": true,
    "categories": ["professional", "personal", "educational"],
    "never_include": ["competitor names", "politics"],
    "always_include": ["one human detail", "one concrete takeaway"]
  },
  "safety_check": {
    "enabled": true,
    "reject_threshold": "any_sensitive_content",
    "notify_on_reject": true
  }
}
```

---

## Safety: What Gets Checked Before Posting

Every piece of content runs through a safety check before it reaches your approval queue. The check is configured per persona — you decide what the rules are.

**What it checks:**
- Does the content match the persona's safety rules?
- Is there anything that could cross-pollinate between personas?
- Does the caption contain any hardcoded personal info (names, handles, emails) that should come from config, not the prompt?

**What happens on a flag:**
- Content moves to `_rejected/` folder
- You get a WhatsApp notification with the reason
- Nothing posts until you explicitly approve

---

## The Golden Rule

> Your most sensitive information is not your API keys. It's the fact that two of your personas exist at all.

FLOWSTATE is designed so that no workflow file, no prompt, and no GitHub commit ever reveals the relationship between your personas. That separation is architectural — it's not something you have to remember to do, it's how the system is built.
