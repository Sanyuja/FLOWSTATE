"""
content_organizer.py
====================
Moves raw content into categorized folders based on CLIP tags.
Only touches files from raw source folders. Already-categorized content is never moved.

ALWAYS run --dry-run first to preview moves before committing.

Usage:
    python content_organizer.py --dry-run     # preview only, nothing moves
    python content_organizer.py               # execute the moves

Output:
    CONTENT_BASE/move_log.csv
"""

import os, sys, shutil, argparse
import pandas as pd
from datetime import datetime
from tqdm import tqdm

# ── CONFIG ────────────────────────────────────────────────────────────────────
BASE_DIR  = os.environ.get("CONTENT_BASE",  "D:\\your-content-folder")
VAULT_DIR = os.environ.get("VAULT_BASE",    "D:\\your-content-folder_vault")

CLIP_CSV    = os.path.join(BASE_DIR, "clip_tags_output.csv")
MOVE_LOG    = os.path.join(BASE_DIR, "move_log.csv")
CAT_DIR     = BASE_DIR                    # categorized subfolders sit in CONTENT_BASE
REVIEW_DIR  = os.path.join(BASE_DIR, "_review")

# Subfolders treated as raw/unprocessed — files here get moved
# CONFIGURE THIS: Add the raw source folder paths where your content lands first.
RAW_ROOTS = [
    os.path.join(BASE_DIR, "raw"),
    os.path.join(BASE_DIR, "imports"),
    os.path.join(BASE_DIR, "camera-roll"),
    os.path.join(BASE_DIR, "phone-uploads"),
]

# ── ROUTING RULES ─────────────────────────────────────────────────────────────
# Priority order: first match wins. Each rule: (field, keywords_any, target_subfolder)
# _VAULT = moves to VAULT_BASE/OF_ready
# _REVIEW = moves to CONTENT_BASE/_review (low confidence, needs manual check)
# Any other string = moves to CONTENT_BASE/<that_string>
#
# CONFIGURE THIS: Edit these rules to match your folder names and content categories.
RULES = [
    # Sensitive / adult → vault first (never hits Instagram)
    ("is_sensitive",  ["true", "yes", True],              "_VAULT"),
    ("platform_fit",  ["adult sensual"],                  "_VAULT"),
    ("outfit",        ["lingerie", "nude", "intimate"],   "_VAULT"),

    # Activity-based
    ("activity", ["drinking coffee", "plating food", "doing nails"],  "lifestyle"),
    ("activity", ["dancing", "pole dancing"],                          "dance"),
    ("activity", ["stretching yoga"],                                  "fitness"),
    ("activity", ["workout", "exercise"],                              "fitness"),
    ("activity", ["playing vr", "coworking", "working on laptop"],    "work"),
    ("activity", ["at concert"],                                       "events"),
    ("activity", ["traveling exploring", "watching sunset"],           "nature"),

    # Pose-based
    ("pose", ["dance"],   "dance"),
    ("pose", ["workout"], "fitness"),

    # Style / location
    ("style",    ["cozy home", "tech productivity"],           "home"),
    ("location", ["home bedroom", "home living"],              "home"),
    ("location", ["outdoor nature", "travel destination"],     "nature"),
    ("location", ["urban city"],                               "street"),

    # Outfit-based fallback
    ("outfit", ["traditional", "elegant dress", "casual everyday",
                "streetwear", "athleisure", "workout fitness"], "fits"),

    # Vibe fallback
    ("vibe", ["travel", "sunset", "scenic"],  "nature"),
    ("vibe", ["editorial", "fashion"],        "fits"),
    ("vibe", ["productive", "cozy"],          "home"),
]


# ── ROUTING LOGIC ─────────────────────────────────────────────────────────────
def decide_folder(row: dict) -> tuple[str, str]:
    for field, keywords, target in RULES:
        val = str(row.get(field, "")).lower().strip()
        if val in ("", "nan"):
            continue
        for kw in keywords:
            if str(kw).lower() in val:
                return target, f"{field}={val!r} matched {kw!r}"
    return "_REVIEW", "no rule matched"


def is_raw(full_path: str) -> bool:
    norm = os.path.normcase(os.path.normpath(full_path))
    for raw in RAW_ROOTS:
        if norm.startswith(os.path.normcase(os.path.normpath(raw))):
            return True
    return False


def safe_dest(dest_dir: str, filename: str) -> str:
    dest = os.path.join(dest_dir, filename)
    if not os.path.exists(dest):
        return dest
    base, ext = os.path.splitext(filename)
    i = 1
    while True:
        candidate = os.path.join(dest_dir, f"{base}_{i}{ext}")
        if not os.path.exists(candidate):
            return candidate
        i += 1


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main(dry_run: bool):
    print("=" * 60)
    print(f"  FLOWSTATE — Content Organizer  {'[DRY RUN]' if dry_run else '[LIVE]'}")
    print("=" * 60)

    if not os.path.exists(CLIP_CSV):
        print(f"[Error] CLIP output not found: {CLIP_CSV}")
        print("  Run content_tagger.py first.")
        sys.exit(1)

    df     = pd.read_csv(CLIP_CSV)
    raw_df = df[df["full_path"].apply(lambda p: is_raw(str(p)) if pd.notna(p) else False)].copy()
    print(f"[Load] {len(df)} total rows. {len(raw_df)} from raw folders.")

    if raw_df.empty:
        print("[Done] Nothing to move.")
        return

    if not dry_run:
        for folder in set(r[2] for r in RULES if r[2] not in ("_VAULT", "_REVIEW")):
            os.makedirs(os.path.join(CAT_DIR, folder), exist_ok=True)
        os.makedirs(os.path.join(VAULT_DIR, "OF_ready"), exist_ok=True)
        os.makedirs(REVIEW_DIR, exist_ok=True)

    move_plan = []
    skipped   = []

    for _, row in raw_df.iterrows():
        src = str(row.get("full_path", ""))
        if not os.path.exists(src):
            skipped.append({"filename": row["filename"], "reason": "source not found"})
            continue

        target_folder, reason = decide_folder(row.to_dict())

        if target_folder == "_VAULT":
            dest_dir = os.path.join(VAULT_DIR, "OF_ready")
        elif target_folder == "_REVIEW":
            dest_dir = REVIEW_DIR
        else:
            dest_dir = os.path.join(CAT_DIR, target_folder)

        move_plan.append({
            "filename":      row["filename"],
            "src":           src,
            "dest":          safe_dest(dest_dir, row["filename"]),
            "target_folder": target_folder,
            "reason":        reason,
        })

    from collections import Counter
    folder_counts = Counter(m["target_folder"] for m in move_plan)
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Move plan:")
    for folder, count in sorted(folder_counts.items()):
        tag = " [vault]" if folder == "_VAULT" else (" [review]" if folder == "_REVIEW" else "")
        print(f"  {folder:<25} {count:>5} files{tag}")
    print(f"  {'─'*35}")
    print(f"  Total to move:         {len(move_plan):>5}")
    print(f"  Skipped (src missing): {len(skipped):>5}")

    if dry_run:
        pd.DataFrame(move_plan).to_csv(MOVE_LOG, index=False)
        print(f"\n[Dry Run] Preview saved to {MOVE_LOG}. Run without --dry-run to execute.")
        return

    print("\n[Move] Starting...")
    moved, errors = 0, []

    for m in tqdm(move_plan, desc="Moving files"):
        try:
            os.makedirs(os.path.dirname(m["dest"]), exist_ok=True)
            shutil.move(m["src"], m["dest"])
            m["status"]   = "moved"
            m["moved_at"] = datetime.now().isoformat()
            moved += 1
        except Exception as e:
            m["status"] = f"error: {e}"
            errors.append(m)

    pd.DataFrame(move_plan).to_csv(MOVE_LOG, index=False)
    print(f"\n[Done] Moved {moved} files.")
    if errors:
        print(f"[Warn] {len(errors)} errors — check {MOVE_LOG}")
    print(f"\nNext: python content_db_updater.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview moves without touching files")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
