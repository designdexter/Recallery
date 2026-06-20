# Recallery — Mac Watcher

Watches your Desktop for new screenshots, sends them to Gemini for analysis, and automatically moves them into organised folders in `~/Pictures/Recallery/`.

No app to open. No manual steps. Take a screenshot — it gets sorted within seconds.

---

## Folder structure it creates

```
~/Pictures/Recallery/
  UI-UX Inspiration/
  General Design/
  Branding/
  Engineering & Concepts/
  Articles & Reading/
  Moodboards/
  Ideas/
  Other/
```

---

## Setup (one time)

**1. Download or clone this folder to your Mac**

**2. Open Terminal and run:**

```bash
cd path/to/recallery-mac
chmod +x setup.sh
./setup.sh
```

It will ask for your Gemini API key (from aistudio.google.com), then install and start the watcher automatically.

**3. That's it.** The watcher runs silently in the background and restarts automatically every time you log in.

---

## Test it

Take a screenshot (Cmd + Shift + 4). Within a few seconds it should disappear from your Desktop and appear in the correct folder inside `~/Pictures/Recallery/`.

Check the log if something doesn't seem right:

```bash
tail -f ~/Library/Logs/recallery.log
```

---

## Stop the watcher

```bash
./uninstall.sh
```

---

## Notes

- Only files whose names start with "Screenshot" are processed — other files on your Desktop are ignored
- If Gemini is unreachable, the screenshot goes to the `Other` folder
- Your Gemini API key is stored in `~/Library/LaunchAgents/com.recallery.watcher.plist` on your Mac — not in any file that gets pushed to GitHub
- No images are uploaded to any server — Gemini analyses the image and returns only text (category + tags)
