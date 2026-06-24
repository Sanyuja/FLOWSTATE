"""
content_tagger.py
=================
Auto-tags your entire content library using OpenCLIP ViT-L-14 + MediaPipe face detection.
Run this first. Output feeds content_refiner.py and content_organizer.py.

Usage:
    python content_tagger.py              # tag all unprocessed files
    python content_tagger.py --rebuild    # retag everything from scratch

Output:
    CONTENT_BASE/clip_tags_output.csv
"""

import os, sys, tempfile, warnings, subprocess, argparse
import pandas as pd
import torch
import open_clip
from PIL import Image
from tqdm import tqdm
import cv2

warnings.filterwarnings("ignore")

# ── CONFIG ────────────────────────────────────────────────────────────────────
BASE_DIR    = os.environ.get("CONTENT_BASE", "D:\\your-content-folder")
OUTPUT_CSV  = os.path.join(BASE_DIR, "clip_tags_output.csv")
CHECKPOINT  = os.path.join(BASE_DIR, "clip_checkpoint.csv")

CLIP_MODEL   = "ViT-L-14"
CLIP_WEIGHTS = "laion2b_s32b_b82k"
BATCH_SIZE   = 32
SKIP_VIDEOS  = False
VIDEO_FRAME  = 1.0   # seconds into video to sample thumbnail

IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.heic'}
VIDEO_EXT = {'.mp4', '.mov', '.mkv', '.avi'}

# Folders to skip (system folders, backups, etc.)
SKIP_DIRS = {"desktop.ini", "Thumbs.db", ".git", "node_modules", "_approved", "_vault"}

# ── CLIP PROMPTS ──────────────────────────────────────────────────────────────
# These prompts define what gets detected. Edit to match your content categories.
# CONFIGURE THIS: Add or remove prompts that match your creator niche.
PROMPTS = {
    "vibe": [
        "clean minimal aesthetic vibe",
        "cozy indoor vibe",
        "sunset golden hour vibe",
        "moody dark atmospheric vibe",
        "bright cheerful vibe",
        "editorial fashion vibe",
        "candid natural vibe",
        "artistic creative vibe",
        "travel adventure vibe",
        "productive work vibe",
    ],
    "outfit": [
        "casual everyday outfit",
        "traditional cultural outfit",
        "workout fitness outfit",
        "lingerie intimate outfit",
        "no outfit implied nude",
        "elegant dress outfit",
        "streetwear casual outfit",
        "athleisure activewear outfit",
    ],
    "pose": [
        "mirror selfie no face",
        "back pose artistic",
        "dance fitness pose",
        "sitting relaxed pose",
        "standing confident pose",
        "lying down pose",
        "workout exercise pose",
        "candid natural moment",
    ],
    "activity": [
        "drinking coffee",
        "working on laptop",
        "playing VR gaming",
        "dancing fitness",
        "cooking plating food",
        "doing nails beauty",
        "stretching yoga",
        "traveling exploring",
        "watching sunset",
        "at concert music event",
        "coworking studying",
    ],
    "location": [
        "city apartment interior",
        "city skyline view",
        "outdoor nature park",
        "gym fitness studio",
        "urban city street",
        "coffee shop cafe",
        "travel destination abroad",
        "home bedroom aesthetic",
        "home living room",
    ],
    "lighting": [
        "golden hour sunset lighting",
        "soft natural window lighting",
        "ring light studio lighting",
        "moody dim lighting",
        "bright outdoor daylight",
        "neon artificial lighting",
        "candlelight warm glow",
    ],
    "style": [
        "minimalist clean aesthetic",
        "cozy home aesthetic",
        "dark moody editorial",
        "bright airy lifestyle",
        "tech productivity setup",
        "fitness wellness aesthetic",
        "travel lifestyle content",
        "sensual intimate aesthetic",
    ],
    "platform_fit": [
        "safe for work lifestyle content",
        "fashion outfit content",
        "fitness wellness content",
        "gaming tech content",
        "food lifestyle content",
        "travel content",
        "adult sensual content",
        "coworking productivity content",
    ],
}

FLAT_PROMPTS  = [p for plist in PROMPTS.values() for p in plist]
PROMPT_TO_CAT = {p: cat for cat, plist in PROMPTS.items() for p in plist}


# ── PLATFORM ROUTING ──────────────────────────────────────────────────────────
def infer_platform_routing(row: dict) -> dict:
    plat = {"X": "", "IG": "", "Threads": "", "Twitch": "", "Reddit": "", "OF": ""}
    outfit       = str(row.get("outfit", "")).lower()
    platform_fit = str(row.get("platform_fit", "")).lower()
    style        = str(row.get("style", "")).lower()
    is_sensitive = row.get("is_sensitive", False)

    if is_sensitive or "nude" in outfit or "lingerie" in outfit or "adult" in platform_fit:
        plat["OF"] = "✓"
        return plat

    if any(k in platform_fit for k in ["lifestyle", "fashion", "food", "travel"]):
        plat.update({"X": "✓", "IG": "✓", "Threads": "✓"})
    if any(k in platform_fit for k in ["fitness", "wellness"]):
        plat.update({"X": "✓", "IG": "✓"})
    if any(k in platform_fit for k in ["gaming", "tech", "coworking"]):
        plat.update({"X": "✓", "Twitch": "✓"})
    if "travel" in platform_fit:
        plat["Reddit"] = "✓"
    if "sensual" in style or "intimate" in style:
        plat["OF"] = "✓"

    if not any(v == "✓" for v in plat.values()):
        plat["X"] = "✓"

    return plat


# ── SETUP ─────────────────────────────────────────────────────────────────────
def setup_clip():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[CLIP] Device: {device}")
    if device == "cuda":
        print(f"[CLIP] GPU: {torch.cuda.get_device_name(0)}")
        print(f"[CLIP] VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    print(f"[CLIP] Loading {CLIP_MODEL} ({CLIP_WEIGHTS})...")
    model, _, preprocess = open_clip.create_model_and_transforms(
        CLIP_MODEL, pretrained=CLIP_WEIGHTS
    )
    model = model.to(device).eval()
    tokenizer = open_clip.get_tokenizer(CLIP_MODEL)

    with torch.no_grad():
        text_tokens   = tokenizer(FLAT_PROMPTS).to(device)
        text_features = model.encode_text(text_tokens)
        text_features /= text_features.norm(dim=-1, keepdim=True)

    print("[CLIP] Model loaded.")
    return model, preprocess, text_features, device


def setup_face_detector():
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    return cv2.CascadeClassifier(cascade_path)


# ── MEDIA UTILS ───────────────────────────────────────────────────────────────
def get_video_thumbnail(video_path: str, at_sec: float = VIDEO_FRAME) -> str | None:
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp.close()
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-ss", str(at_sec), "-i", video_path,
             "-frames:v", "1", "-q:v", "2", tmp.name],
            capture_output=True, timeout=20
        )
        if result.returncode == 0 and os.path.getsize(tmp.name) > 0:
            return tmp.name
    except subprocess.TimeoutExpired:
        print(f"[Video] Timeout (skipping): {video_path}")
    except FileNotFoundError:
        print("[Video] ffmpeg not found in PATH — skipping video thumbnails")
    except Exception as e:
        print(f"[Video] {video_path}: {e}")
    try:
        os.unlink(tmp.name)
    except Exception:
        pass
    return None


def detect_face(image_path: str, detector) -> bool:
    try:
        img = cv2.imread(image_path)
        if img is None:
            return False
        gray  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
        return len(faces) > 0
    except Exception:
        return False


def classify_image(image_path, model, preprocess, text_features, device, top_k=3):
    try:
        img = preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0).to(device)
        with torch.no_grad():
            img_features = model.encode_image(img)
            img_features /= img_features.norm(dim=-1, keepdim=True)
            sims = (img_features @ text_features.T).squeeze(0).cpu()

        top_idx     = sims.topk(top_k * len(PROMPTS)).indices.tolist()
        top_prompts = [FLAT_PROMPTS[i] for i in top_idx]

        result = {cat: "" for cat in PROMPTS}
        for p in top_prompts:
            cat = PROMPT_TO_CAT.get(p)
            if cat and not result[cat]:
                result[cat] = p
        return result
    except Exception as e:
        print(f"[CLIP] Error on {image_path}: {e}")
        return {cat: "" for cat in PROMPTS}


def collect_files(base_dir: str) -> pd.DataFrame:
    rows = []
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel_root     = os.path.relpath(root, base_dir)
        folder_label = rel_root.replace("\\", "/")

        # Anything in vault/OF subfolders is flagged sensitive automatically
        is_sensitive = any(k in folder_label.lower() for k in ["vault", "of_ready", "watermarked", "nsfw"])

        for f in files:
            if f.startswith("."):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext not in IMAGE_EXT and ext not in VIDEO_EXT:
                continue
            rows.append({
                "filename":     f,
                "full_path":    os.path.join(root, f),
                "folder_label": folder_label,
                "type":         "photo" if ext in IMAGE_EXT else "video",
                "format":       ext.lstrip("."),
                "is_sensitive": is_sensitive,
            })

    return pd.DataFrame(rows)


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main(rebuild: bool = False):
    print("=" * 60)
    print("  FLOWSTATE — Content Tagger")
    print("=" * 60)

    done_files = set()
    results    = []

    if not rebuild and os.path.exists(CHECKPOINT):
        ckpt       = pd.read_csv(CHECKPOINT)
        done_files = set(ckpt["filename"].tolist())
        results    = ckpt.to_dict("records")
        print(f"[Checkpoint] Resuming — {len(done_files)} already processed.")

    print(f"\n[Scan] Walking {BASE_DIR}...")
    df   = collect_files(BASE_DIR)
    todo = df[~df["filename"].isin(done_files)].copy()

    if SKIP_VIDEOS:
        todo = todo[todo["type"] == "photo"]

    print(f"[Scan] {len(df)} total media files. {len(todo)} to process.\n")

    if todo.empty:
        print("[Done] Nothing new to tag.")
        return

    todo = todo.sort_values(["folder_label", "filename"]).reset_index(drop=True)

    model, preprocess, text_features, device = setup_clip()
    face_detector = setup_face_detector()
    tmp_paths = []

    try:
        for i, row in tqdm(todo.iterrows(), total=len(todo), desc="Tagging"):
            full_path = row["full_path"]

            if row["type"] == "video":
                img_path = get_video_thumbnail(full_path)
                if img_path:
                    tmp_paths.append(img_path)
                else:
                    result_row = row.to_dict()
                    result_row.update({cat: "" for cat in PROMPTS})
                    result_row["face_detected"] = ""
                    result_row.update(infer_platform_routing(result_row))
                    result_row["label_status"] = "unlabeled"
                    results.append(result_row)
                    continue
            else:
                img_path = full_path

            labels     = classify_image(img_path, model, preprocess, text_features, device)
            face       = detect_face(img_path, face_detector)
            result_row = row.to_dict()
            result_row.update(labels)
            result_row["face_detected"] = "YES" if face else ""
            result_row["label_status"]  = "labeled"
            result_row.update(infer_platform_routing(result_row))
            results.append(result_row)

            if len(results) % 100 == 0:
                pd.DataFrame(results).to_csv(CHECKPOINT, index=False)
                tqdm.write(f"  [Checkpoint] {len(results)} rows saved.")

    finally:
        for t in tmp_paths:
            try:
                os.unlink(t)
            except Exception:
                pass

    out_df = pd.DataFrame(results)
    out_df.to_csv(OUTPUT_CSV, index=False)
    print(f"\n[Done] {len(out_df)} rows saved to {OUTPUT_CSV}")

    if os.path.exists(CHECKPOINT):
        os.remove(CHECKPOINT)

    print("\nNext: python content_refiner.py   (enrich hero images with Claude Vision)")
    print("Then: python content_organizer.py  (move files to categorized folders)")
    print("Then: python content_db_updater.py (build master DB + content_inventory.json)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true", help="Retag all files from scratch")
    args = parser.parse_args()
    main(rebuild=args.rebuild)
