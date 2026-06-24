# Contributing to FLOWSTATE

Thank you. This project is most useful when it covers a wide range of creator types, not just one person's use case.

---

## What's most valuable to contribute

**Persona config examples**
The best contributions are real or realistic `persona.example.json` files for different creator types. Examples that would be immediately useful:

- Fitness/gym creator (Instagram + YouTube Shorts)
- Food blogger (Instagram + TikTok)
- Business/thought leadership (LinkedIn + Threads)
- Gaming streamer (Twitch + YouTube + Instagram)
- Artist/illustrator (Instagram + Behance)
- Musician (Instagram + YouTube + TikTok)

Add these to `config/examples/` as `persona-[type].example.json`.

**Platform connectors**
The current free stack covers Instagram and Threads. Contributions for additional platform connectors are welcome:

- YouTube Shorts (video upload via YouTube Data API)
- TikTok (TikTok for Developers API)
- LinkedIn (company page posting)
- Pinterest

Add new platform logic as modular code blocks that can be inserted into the approval handler workflow.

**Linux/Mac setup**
The current setup scripts are Windows PowerShell. Shell script equivalents for Linux/Mac would make this accessible to more users.

**Bug fixes and improvements**
Open an issue first for anything that changes existing workflow behavior.

---

## How to contribute

1. Fork the repo
2. Create a branch: `git checkout -b feature/your-thing`
3. Make your changes
4. Open a pull request with a clear description of what it does and why

Keep PRs focused. One thing per PR.

---

## What not to contribute

- Actual API keys, real folder paths, or personal content
- Persona configs containing real voice briefs tied to a real person without permission
- Changes that break the existing n8n workflow structure without a migration path

---

## Questions

Open a GitHub issue. Describe what you're trying to do and where you're stuck.
