"""
content_refiner.py
==================
Enriches hero images with Claude Haiku Vision — richer labels + ready-to-post captions.
Run after content_tagger.py.

Setup:
    Set ANTHROPIC_API_KEY environment variable.
    Set PERSONA_VOICE_BRIEF environment variable (or put it in config/persona.json).

Usage:
    python content_refiner.py

Output:
    CONTENT_BASE/claude_refined_output.csv   — enriched labels
    CONTENT_BASE/captions_output.csv         — platform captions
"""

import os, base64, json, time
import pandas as pd
from PIL import Image
from tqdm import tqdm
import anthropic

# ── CONFIG ────────────────────────────────────────────────────────────────────
BASE_DIR         = os.environ.get("CONTENT_BASE", "D:\\your-content-folder")
SCRIPTS_DIR      = os.environ.get("SCRIPTS_DIR",  "D:\\your-content-folder\\scripts")
CLIP_OUTPUT      = os.path.join(BASE_DIR, "clip_tags_output.csv")
REFINED_OUTPUT   = os.path.join(BASE_DIR, "claude_refined_output.csv")
CAPTIONS_OUTPUT  = os.path.join(BASE_DIR, "captions_output.csv")

HEROES_PER_CAT   = 5
REVIEW_STATUSES  = {"labeled", "unlabeled"}
MAX_IMAGE_PX     = 1024
SLEEP_BETWEEN    = 0.5


# ── LOAD PERSONA VOICE BRIEF ──────────────────────────────────────────────────
def load_voice_brief() -> str:
    """
    Tries three sources in order:
    1. PERSONA_VOICE_BRIEF env var
    2. config/persona.json voice_brief field (looks in SCRIPTS_DIR/../config/)
    3. Falls back to a generic placeholder that still produces usable output
    """
    brief = os.environ.get("PERSONA_VOICE_BRIEF", "").strip()
    if brief:
        return brief

    persona_path = os.path.join(
        os.path.dirname(SCRIPTS_DIR), "config", "persona.json"
    )
    if os.path.exists(persona_path):
        try:
            with open(persona_path) as f:
                data = json.load(f)
            brief = data.get("persona", {}).get("voice_brief", "").strip()
            if brief:
                print(f"[Refiner] Loaded voice brief from {persona_path}")
                return brief
        except Exception:
            pass

    print("[Refiner] WARNING: No voice brief found. Set PERSONA_VOICE_BRIEF env var")
    print("          or fill in persona.voice_brief in config/persona.json.")
    print("          Using generic fallback — captions will be less personalized.\n")
    return (
        "Authentic, concise, understated. No hashtag spam in captions. "
        "Platform-appropriate tone. Never corporate. Short punchy lines."
    )


# ── SETUP ─────────────────────────────────────────────────────────────────────
def get_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(env_path):
            for line in open(env_path):
                if line.startswith("ANTHROPIC_API_KEY="):
                    api_key = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not api_key:
        raise ValueError(
            "Set ANTHROPIC_API_KEY environment variable.\n"
            "  Windows: [System.Environment]::SetEnvironmentVariable('ANTHROPIC_API_KEY', 'sk-ant-...', 'Machine')"
        )
    return anthropic.Anthropic(api_key=api_key)


# ── IMAGE UTILS ───────────────────────────────────────────────────────────────
def image_to_base64(path: str, max_px: int = MAX_IMAGE_PX) -> tuple[str, str]:
    import io
    img = Image.open(path).convert("RGB")
    w, h = img.size
    if max(w, h) > max_px:
        ratio = max_px / max(w, h)
        img   = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.standard_b64encode(buf.getvalue()).decode(), "image/jpeg"


# ── LABEL ENRICHMENT ──────────────────────────────────────────────────────────
LABEL_PROMPT = """{voice_brief}

Look at this image and provide enriched content labels as JSON.
Current CLIP labels (may be rough): {clip_labels}

Return ONLY valid JSON:
{{
  "vibe":       "one short phrase describing the overall feel",
  "outfit":     "what is being worn (or 'no outfit' if implied)",
  "pose":       "body position or pose",
  "activity":   "what is happening",
  "location":   "where this is",
  "lighting":   "lighting type and quality",
  "style":      "content aesthetic style",
  "is_sensitive": true or false,
  "platform_fit": {{
    "X": true or false,
    "IG": true or false,
    "Threads": true or false,
    "Twitch": true or false,
    "Reddit": true or false,
    "OF": true or false
  }},
  "notes": "one sentence of useful context for content planning"
}}

Be concise. Keep all text under 10 words per field. JSON only, no extra text.
"""

def enrich_labels(client, image_path: str, clip_row: dict, voice_brief: str) -> dict:
    clip_labels = {k: clip_row.get(k, "")
                   for k in ["vibe","outfit","pose","activity","location","lighting","style"]}
    try:
        img_b64, media_type = image_to_base64(image_path)
    except Exception as e:
        print(f"  [Image error] {image_path}: {e}")
        return {}

    prompt = LABEL_PROMPT.format(
        voice_brief=voice_brief,
        clip_labels=json.dumps(clip_labels, indent=2)
    )

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64",
                     "media_type": media_type, "data": img_b64}},
                    {"type": "text",  "text": prompt},
                ]
            }]
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        print(f"  [Claude error] {e}")
        return {}


# ── CAPTION GENERATION ────────────────────────────────────────────────────────
CAPTION_PROMPT = """{voice_brief}

Look at this image. Generate ready-to-post captions for the platforms marked True.
Platform fit: {platform_fit}
Labels: {labels}

Return ONLY valid JSON:
{{
  "X":       "tweet — max 240 chars, personality, no hashtag spam",
  "IG":      "instagram caption — 1-3 sentences, aesthetic, 3-5 hashtags at end",
  "Threads": "casual thread — conversational, 1-2 sentences, honest",
  "Twitch":  "stream title — short, inviting, sets clear expectation",
  "Reddit":  "reddit post title — value-first, no obvious self-promo",
  "OF":      "intimate caption — warm, personal, max 2 sentences"
}}

Only fill platforms marked True. Leave others as empty string "". JSON only.
"""

def generate_captions(client, image_path: str, refined_row: dict, voice_brief: str) -> dict:
    platform_fit = {
        p: refined_row.get(p, "") == "✓"
        for p in ["X","IG","Threads","Twitch","Reddit","OF"]
    }
    labels = {k: refined_row.get(k, "")
              for k in ["vibe","outfit","activity","location","style"]}

    try:
        img_b64, media_type = image_to_base64(image_path)
    except Exception as e:
        return {p: "" for p in ["X","IG","Threads","Twitch","Reddit","OF"]}

    prompt = CAPTION_PROMPT.format(
        voice_brief=voice_brief,
        platform_fit=json.dumps(platform_fit),
        labels=json.dumps(labels)
    )

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=768,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64",
                     "media_type": media_type, "data": img_b64}},
                    {"type": "text",  "text": prompt},
                ]
            }]
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        print(f"  [Caption error] {e}")
        return {p: "" for p in ["X","IG","Threads","Twitch","Reddit","OF"]}


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  FLOWSTATE — Content Refiner (Claude Vision)")
    print("=" * 60)

    if not os.path.exists(CLIP_OUTPUT):
        print(f"[Error] CLIP output not found: {CLIP_OUTPUT}")
        print("  Run content_tagger.py first.")
        return

    voice_brief = load_voice_brief()

    df = pd.read_csv(CLIP_OUTPUT)
    print(f"[Load] {len(df)} rows from CLIP output.")

    sfw_df  = df[df["is_sensitive"] != True].copy()
    sens_df = df[df["is_sensitive"] == True].copy()

    heroes_sfw  = sfw_df[sfw_df["type"] == "photo"].groupby("folder_label").head(HEROES_PER_CAT)
    heroes_sens = sens_df[sens_df["type"] == "photo"].groupby("folder_label").head(HEROES_PER_CAT)
    heroes      = pd.concat([heroes_sfw, heroes_sens]).reset_index(drop=True)
    print(f"[Heroes] {len(heroes)} images selected for Vision review.")

    done_files      = set()
    refined_results = []
    caption_results = []
    if os.path.exists(REFINED_OUTPUT):
        existing    = pd.read_csv(REFINED_OUTPUT)
        done_files  = set(existing["filename"].tolist())
        refined_results = existing.to_dict("records")
        print(f"[Resume] {len(done_files)} already refined.")

    heroes_todo = heroes[~heroes["filename"].isin(done_files)]
    print(f"[Queue] {len(heroes_todo)} images to enrich.\n")

    client = get_client()

    for _, row in tqdm(heroes_todo.iterrows(), total=len(heroes_todo), desc="Refining"):
        full_path = row.get("full_path", "")
        if not os.path.exists(full_path):
            continue

        row_dict = row.to_dict()

        enriched = enrich_labels(client, full_path, row_dict, voice_brief)
        time.sleep(SLEEP_BETWEEN)

        if enriched:
            for k, v in enriched.items():
                if k == "platform_fit" and isinstance(v, dict):
                    for plat, fits in v.items():
                        row_dict[plat] = "✓" if fits else ""
                elif k != "platform_fit":
                    row_dict[k] = v
            row_dict["label_status"] = "confirmed"
            refined_results.append(row_dict)

            captions = generate_captions(client, full_path, row_dict, voice_brief)
            time.sleep(SLEEP_BETWEEN)

            caption_results.append({
                "filename":        row_dict["filename"],
                "full_path":       full_path,
                "folder_label":    row_dict.get("folder_label", ""),
                "caption_X":       captions.get("X", ""),
                "caption_IG":      captions.get("IG", ""),
                "caption_Threads": captions.get("Threads", ""),
                "caption_Twitch":  captions.get("Twitch", ""),
                "caption_Reddit":  captions.get("Reddit", ""),
                "caption_OF":      captions.get("OF", ""),
            })

        if len(refined_results) % 10 == 0:
            pd.DataFrame(refined_results).to_csv(REFINED_OUTPUT, index=False)
            pd.DataFrame(caption_results).to_csv(CAPTIONS_OUTPUT, index=False)

    if refined_results:
        pd.DataFrame(refined_results).to_csv(REFINED_OUTPUT, index=False)
    if caption_results:
        pd.DataFrame(caption_results).to_csv(CAPTIONS_OUTPUT, index=False)

    print(f"\n[Done] {len(refined_results)} images refined. {len(caption_results)} caption sets generated.")
    print(f"\nNext: python content_db_updater.py")


if __name__ == "__main__":
    main()
