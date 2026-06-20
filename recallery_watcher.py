#!/usr/bin/env python3
"""
Recallery Mac Watcher
Watches your Desktop for new screenshots, sends them to Gemini for analysis,
and automatically moves them into organised folders.
"""

import os
import sys
import time
import shutil
import logging
import base64
import json
import re
from pathlib import Path

import urllib.request
import urllib.error

# ── Configuration ────────────────────────────────────────────────────────────

WATCH_FOLDER = Path.home() / "Desktop"

SORTED_FOLDER = Path.home() / "Pictures" / "Recallery"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

CATEGORIES = {
    "uiux":        "UI-UX Inspiration",
    "general":     "General Design",
    "branding":    "Branding",
    "engineering": "Engineering & Concepts",
    "articles":    "Articles & Reading",
    "moodboard":   "Moodboards",
    "ideas":       "Ideas",
    "other":       "Other",
}

# Only process files that look like screenshots
SCREENSHOT_PREFIXES = ("Screenshot", "Screen Shot", "screenshot", "Capture")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

LOG_FILE = Path.home() / "Library" / "Logs" / "recallery.log"

# Minimum seconds between Gemini API calls (avoid bursting through rate limits)
MIN_API_INTERVAL = 5
_last_api_call = 0.0

# ── Logging ──────────────────────────────────────────────────────────────────

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("recallery")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _throttle():
    """Wait if needed to respect rate limits."""
    global _last_api_call
    now = time.time()
    elapsed = now - _last_api_call
    if elapsed < MIN_API_INTERVAL:
        time.sleep(MIN_API_INTERVAL - elapsed)
    _last_api_call = time.time()


def is_screenshot(path: Path) -> bool:
    """Return True if the file looks like a Mac screenshot."""
    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        return False
    return any(path.name.startswith(p) for p in SCREENSHOT_PREFIXES)


def analyse_with_gemini(image_path: Path) -> dict:
    """Send image to Gemini and get back category + tags + title."""
    if not GEMINI_API_KEY:
        log.warning("GEMINI_API_KEY not set — using 'other' category")
        return {"category": "other", "title": image_path.stem, "tags": []}

    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    ext = image_path.suffix.lower()
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "gif": "image/gif", "webp": "image/webp"}.get(ext.lstrip("."), "image/png")

    prompt = (
        "Analyse this screenshot and return ONLY a JSON object with these fields:\n"
        "- \"title\": short descriptive title (max 7 words)\n"
        "- \"category\": pick the single best fit from: "
        "uiux (UI/UX design inspiration), "
        "general (general design, typography, layout), "
        "branding (logos, brand identity, colour palettes), "
        "engineering (code, architecture, technical concepts, diagrams), "
        "articles (articles, text-heavy content, reading), "
        "moodboard (mood, aesthetic, photography inspiration), "
        "ideas (product ideas, sketches, concepts), "
        "other (anything that doesn't fit)\n"
        "- \"tags\": array of 3-5 lowercase keyword tags\n\n"
        "Return only raw JSON. No markdown. No explanation."
    )

    payload = json.dumps({
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime, "data": image_data}},
            ]
        }]
    }).encode("utf-8")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    )

    max_retries = 3
    for attempt in range(max_retries):
        _throttle()
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            text = re.sub(r"```json|```", "", text).strip()
            parsed = json.loads(text)
            if parsed.get("category") not in CATEGORIES:
                parsed["category"] = "other"
            return parsed
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
            log.error(f"Gemini HTTP {e.code} (attempt {attempt+1}/{max_retries}): {e.reason} — {body}")
            if e.code == 429 and attempt < max_retries - 1:
                wait = 10 * (attempt + 1)  # 10s, 20s
                log.info(f"  Rate limited, retrying in {wait}s…")
                time.sleep(wait)
                continue
            return {"category": "other", "title": image_path.stem, "tags": []}
        except Exception as e:
            log.error(f"Gemini error (attempt {attempt+1}/{max_retries}): {e}")
            return {"category": "other", "title": image_path.stem, "tags": []}


def move_screenshot(image_path: Path, analysis: dict) -> Path:
    """Move screenshot into the correct Recallery subfolder."""
    cat_key = analysis.get("category", "other")
    folder_name = CATEGORIES.get(cat_key, CATEGORIES["other"])
    dest_folder = SORTED_FOLDER / folder_name
    dest_folder.mkdir(parents=True, exist_ok=True)

    # Keep original filename, avoid overwrites
    dest = dest_folder / image_path.name
    counter = 1
    while dest.exists():
        dest = dest_folder / f"{image_path.stem}_{counter}{image_path.suffix}"
        counter += 1

    shutil.move(str(image_path), str(dest))
    return dest


# ── Watcher ───────────────────────────────────────────────────────────────────

def watch():
    log.info("Recallery watcher started")
    log.info(f"  Watching : {WATCH_FOLDER}")
    log.info(f"  Sorting into : {SORTED_FOLDER}")

    if not GEMINI_API_KEY:
        log.warning("  GEMINI_API_KEY is not set — screenshots will go to 'Other' folder")

    # Track files we've already seen to avoid double-processing
    seen: set[str] = set()

    # Seed with files already on Desktop so we don't process old ones
    for f in WATCH_FOLDER.iterdir():
        seen.add(f.name)

    log.info(f"  Seeded {len(seen)} existing files — watching for new screenshots…")

    while True:
        try:
            current = set(f.name for f in WATCH_FOLDER.iterdir())
            new_files = current - seen

            for name in new_files:
                path = WATCH_FOLDER / name
                seen.add(name)

                if not is_screenshot(path):
                    continue

                # Wait a moment to ensure the file is fully written
                time.sleep(1.5)

                if not path.exists():
                    continue

                log.info(f"New screenshot detected: {name}")
                analysis = analyse_with_gemini(path)
                log.info(f"  → Category: {analysis.get('category')} | Title: {analysis.get('title')} | Tags: {analysis.get('tags')}")

                dest = move_screenshot(path, analysis)
                log.info(f"  → Moved to: {dest}")

        except Exception as e:
            log.error(f"Watcher error: {e}")

        time.sleep(2)  # Poll every 2 seconds


def reprocess():
    """Re-classify all files currently in the Other folder."""
    other_folder = SORTED_FOLDER / CATEGORIES["other"]
    if not other_folder.exists():
        log.info("No 'Other' folder found — nothing to reprocess.")
        return

    files = [f for f in other_folder.iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS]
    if not files:
        log.info("No image files in 'Other' folder.")
        return

    log.info(f"Re-processing {len(files)} files from Other…")
    moved = 0
    for path in files:
        log.info(f"  Analysing: {path.name}")
        analysis = analyse_with_gemini(path)
        cat = analysis.get("category", "other")
        log.info(f"    → Category: {cat} | Title: {analysis.get('title')} | Tags: {analysis.get('tags')}")

        if cat != "other":
            dest = move_screenshot(path, analysis)
            log.info(f"    → Moved to: {dest}")
            moved += 1
        else:
            log.info(f"    → Staying in Other")

        # Delay between files to stay within rate limits
        time.sleep(5)

    log.info(f"Done. Moved {moved}/{len(files)} files out of Other.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--reprocess":
        reprocess()
    else:
        watch()
