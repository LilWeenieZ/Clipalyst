# ✂️ Clipalyst
### The AI-powered clipboard manager that remembers everything — so you don't have to.

---

## The Problem

Your clipboard holds one item.  
Every developer, writer, designer, and analyst copies dozens of things every hour. Most of it vanishes the moment you copy something new — gone forever.

The old workaround: paste into a document, switch apps, hunt it down later.  
The real answer: **a clipboard that becomes smarter the more you use it.**

---

## What Is Clipalyst?

Clipalyst is a **Windows clipboard manager** that silently captures everything you copy, tags it automatically with AI, and surfaces exactly what you need — in under a second — via a beautiful keyboard-driven search interface.

No cloud. No subscription required to get started. Nothing to think about.

---

## How It Works

```
Copy anything  →  Clipalyst captures it  →  AI tags it instantly
                                            ↓
                              Hit your hotkey  →  search + paste
```

1. **Silent capture** — a lightweight background process monitors your clipboard at 500 ms intervals. It ignores apps you tell it to (password managers, private browsers).
2. **AI tagging** — every item is classified in the background: `code`, `url`, `email`, `api_key`, `path`, `address`, `phone`, `number`, or plain `text`. No manual filing.
3. **Instant search** — summon the search window with a global hotkey (`Ctrl+Alt+V` by default, fully customisable). Filter your entire history as you type. Click to copy, right-click for more.

---

## Key Features

| Feature | Free | Pro (⭐) |
|---|---|---|
| Clipboard history | 50 items | Up to 5 000 items |
| AI auto-tagging | ✅ | ✅ |
| Pinned items | 3 | Unlimited |
| Global hotkey (customisable) | ✅ | ✅ |
| Launch at Windows startup | ✅ | ✅ |
| Pause / resume monitoring | ✅ | ✅ |
| Custom AI model & API key | ❌ | ✅ |
| Activation key licence | — | Email delivery |

### Standout Capabilities

- **API Key & Secret Detection** — local HMAC-pattern matching catches tokens before they even reach the AI, so sensitive data is classified instantly and never leaves the machine unnecessarily.
- **Windows Path Recognition** — drive paths (`C:\Users\…`) and UNC paths (`\\server\share`) are detected and tagged automatically.
- **Per-app Ignore List** — tell Clipalyst to never capture from 1Password, your browser's incognito mode, or any other app. Privacy first.
- **Auto-delete policy** — set history to auto-purge after 7, 30, or 90 days, or keep it forever.
- **Zero cloud dependency** — history lives in a local SQLite database. Your data never leaves your machine.
- **Serverless licence validation** — Pro keys are validated offline via HMAC-SHA256 with a 180-day rolling window. No phone-home, no internet required to stay activated.

---

## The Interface

A **frameless, dark-mode search window** appears in the top-centre of your screen, keyboard-first and distraction-free:

- Type to filter across content, tags, and labels in real time
- One click copies to clipboard
- Right-click for Pin, Delete, or Copy
- Pinned items always float to the top
- Live AI tagging status so you know the engine is working
- Subscription tier badge and item counter always visible

Dismiss with `Escape`. The window hides, not closes — zero startup latency next time.

---

## Who It's For

| Persona | Pain solved |
|---|---|
| **Developers** | Never lose a stack trace, error message, token, or path again |
| **Writers & editors** | Stop pasting into scratchpads to hold quotes and snippets |
| **Researchers** | Accumulated web clippings, citations, and URLs — all searchable |
| **Designers** | Hex codes, font names, and asset paths at your fingertips |
| **Power users** | One hotkey to rule every copy you've ever made |

---

## Business Model

**Free tier** converts users at zero cost. The hard limit of 50 items creates natural upgrade pressure for anyone who copies more than a screen's worth of content per session — which is nearly every power user.

**Pro** is a one-time activation key delivered by email. No recurring subscription, no account wall. This dramatically reduces churn friction while maintaining a clean revenue event.

The **custom AI model** Pro feature is a force-multiplier: Pro users can bring their own Anthropic API key and swap to any Claude model, turning Clipalyst into an extensible AI layer on top of the clipboard.

---

## Technical Stack

- **Python + CustomTkinter** — native Windows feel, single-file binary distribution via PyInstaller
- **SQLite** — embedded, zero-config local database
- **Anthropic Claude** (claude-haiku-4-5 default) — fast, cheap, accurate classification
- **pystray + Pillow** — system tray integration with a custom icon
- **HMAC-SHA256** — offline licence validation with no server required

---

## Traction & Next Steps

- ✅ Core feature-complete: capture, tag, search, pin, delete, settings, licence
- ✅ Distributable Windows binary via PyInstaller
- 🔜 Auto-updater
- 🔜 Statistics dashboard (items saved this week, most frequent sources)
- 🔜 Snippet templates (store a copy as a reusable template)
- 🔜 Mac support

---

> *"The best clipboard manager is the one you never have to think about."*  
> — Clipalyst design principle
