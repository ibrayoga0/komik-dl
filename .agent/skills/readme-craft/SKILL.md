---
name: readme-craft
description: Craft README.md files (and other project docs like CONTRIBUTING.md, docs/*.md) that read like a maintainer wrote them, not like a template an AI filled in. Use this whenever the user asks to write, generate, improve, or "make more professional" a README, project documentation, or repo docs — even if they just say "buatin README" or "dokumentasi projectnya". Covers structure, section selection based on project type, badges, code examples, and avoiding generic AI-README patterns (wall-of-bullets, empty "Contributing" sections, fake badges, feature lists with no context). Pair with stop-slop for the prose inside each section.
---

# README Craft

Write README.md files that sound like someone who actually built and uses the project wrote them — not a template with the project name swapped in.

## Why generic AI READMEs feel wrong

Before writing anything, know what to avoid. The tells:

- **Bullet-point feature dumps** with no explanation of why any feature matters ("✨ Fast", "🚀 Scalable", "💪 Robust")
- **Every section from a mental template**, regardless of whether the project needs it (a 200-line personal script does not need a "Roadmap" or "Code of Conduct" section)
- **Badges that don't correspond to anything real** (a license badge for a repo with no LICENSE file, a build-passing badge with no CI configured)
- **Installation instructions with no actual command tested against the repo** — generic `npm install` / `pip install -r requirements.txt` guesses instead of checking what's actually there
- **A "Contributing" section that says nothing** ("Contributions are welcome! Please open a PR.") on a solo hobby project that clearly isn't looking for contributors
- **Title-case emoji headers on every single section** (📦 Installation, 🚀 Usage, 📝 License) — used consistently everywhere, this reads as decoration, not signal
- **Overpromising tone** — calling a weekend script "enterprise-grade" or "production-ready"

The fix is not "remove all structure." It's: only include what's true and useful for *this* project, and write each part like you'd explain it to a friend over Discord.

## Step 1: Investigate before writing

Never write a README from the project name alone. Read the actual repo first:

1. **Read the entry point / main files** — understand what the project actually does, not what you assume from the name
2. **Check for a package manifest** (`package.json`, `requirements.txt`, `Cargo.toml`, `composer.json`, etc.) — pull the real install command, real dependencies, real scripts (`npm run dev`, not a guess)
3. **Check for existing config files** that hint at tooling — `.env.example`, `docker-compose.yml`, CI config (`.github/workflows/`), test setup
4. **Check for a LICENSE file** — only add a license badge/section if one actually exists; ask the user if they want one added if not
5. **Look at recent commits or code comments** if available — real quirks and constraints of the project (e.g. "requires Aternos hosting", "MoonLoader-only") belong in the README, generic ones don't
6. **Ask the user directly** if the project's *purpose* or *target audience* isn't obvious from the code — a personal tool for one Discord server needs a very different README than a public npm package

If any of this can't be inspected (user is describing a project verbally, no files present), ask targeted questions instead of inventing details — see "When information is missing" below.

## Step 2: Pick sections based on project type, not a fixed template

Don't include every possible README section. Match sections to what the project actually is:

| Project type | Sections that usually earn their place | Sections to usually skip |
|---|---|---|
| Personal script / bot / automation tool | What it does & why, Setup, Usage, Config, Known limitations | Contributing, Code of Conduct, Roadmap, Badges (unless CI exists) |
| Open-source library / package | What it does, Install, Quick start, API reference or link to docs, License | — |
| Team-internal tool | What it does, Setup, Usage, Who to ask for help | Public Contributing/CoC boilerplate |
| Web app / SaaS-ish project | What it does, Screenshots/demo link, Setup, Env vars, Deployment | Full API reference (link to separate docs instead) |
| Learning project / experiment | What it is, What you learned or tried, How to run it | Contributing, Roadmap, Badges |

When unsure which bucket a project falls into, ask the user rather than defaulting to the full "professional open-source" template — that default is exactly what makes AI READMEs feel generic.

## Step 3: Write each section like a person explaining their own project

General rules:

- **Open with what the thing does and why it exists**, in plain sentences — not a tagline, not a bullet list. One or two sentences a stranger could understand without reading the code.
- **Skip the feature-emoji-bullet-list.** If you want to mention capabilities, weave them into a sentence or use a plain list without decorative emoji on every line.
- **Every code example must be something that actually runs.** Pull commands from the real manifest/scripts, not invented placeholders like `your-command-here`.
- **Write limitations and known issues honestly** if they exist — "this only works with Aternos free-tier hosting" is more useful and more human than pretending the project is universally robust.
- **Match section headers to plain language** — "How it works" reads more human than "🔧 Architecture Overview"; use emoji sparingly if at all, and never as a rule applied to every header.
- **Keep a "why" note where it matters** — a one-line "built this because X was annoying to do manually" does more for a personal project's README than any badge.
- After drafting prose-heavy sections (the intro, the "why", any longer paragraph), apply the **stop-slop** skill's rules directly — cut filler openers, adverbs, passive voice, and vague declaratives before finalizing.

## Step 4: Structure and formatting details

- **Table of contents**: only for READMEs long enough to need one (roughly 5+ major sections). Skip it on short READMEs — it's dead weight.
- **Badges**: only include ones backed by something real (actual CI, actual published package, actual license file). Never add a badge as pure decoration.
- **Code blocks**: always tag the language for syntax highlighting (` ```bash `, ` ```js `, etc).
- **Screenshots/GIFs**: strongly recommend for anything with a UI. Note to the user where to place one if they don't have it ready yet — don't fabricate an image.
- **Headings**: sentence case reads more natural than Title Case Everywhere ("Getting started" not "Getting Started") — but match whatever convention the user's other docs already use, if any exist.

## Step 5: When information is missing

Don't invent install steps, license terms, or contact info. If something essential is missing:

- Ask the user directly (one focused question, not a long form)
- Or leave a clearly marked placeholder like `<!-- TODO: add deployment steps -->` so it's obvious to the user what's still needed, rather than silently guessing

## Step 6: Final pass

Before delivering the README:

1. Re-read it as if you're a stranger who found this repo — does the first paragraph tell you what it is and whether you need it?
2. Check every command/code block is copy-pasteable and real
3. Check no section exists just because "READMEs usually have this"
4. Run the stop-slop quick-checks (adverbs, passive voice, vague declaratives, punchy pull-quote endings) over the prose sections
5. Confirm badges and links actually resolve to real things in this project, not placeholders