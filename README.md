# ✂️ Clipalyst

### The AI-powered clipboard manager that remembers everything — so you don't have to.

Clipalyst is a professional **Windows clipboard manager** that captures everything you copy, tags it automatically with AI, and surfaces it instantly via a beautiful keyboard-driven interface.

![Clipalyst Logo](assets/icon.ico) 

## ✨ Features

- 🔋 **Silent Capture** — Lightweight background process (500ms intervals).
- 🧠 **AI Auto-Tagging** — Classified as `code`, `url`, `email`, `api_key`, `path`, etc.
- 🔍 **Instant Search** — Summond via global hotkey (`Ctrl+Alt+V`).
- 🛡️ **Privacy First** — Per-app ignore list (e.g., password managers).
- 📂 **Zero Cloud** — Local SQLite database. Your data never leaves your machine.
- ⭐ **Pro Features** — 5,000 items history, custom AI models, and unlimited pins. 

## 🚀 Getting Started

### Prerequisites

- Windows 10/11
- Python 3.9+ (if running from source)
- Anthropic API Key (optional, for AI tagging)

### Installation
## Method 1
1.  **[Download](https://github.com/LilWeenieZ/Clipalyst/releases) latest Release**
    
2.  Run installer
   
3.  Add ANTHROPIC_API_KEY to Environmental Variables
   
    Press 'Win+R' to open Run and enter:
    
    `rundll32 sysdm.cpl,EditEnvironmentVariables`
    
    (Environmental Variables window should appear)
    
    In 'User variables' click on 'New...' and enter:

    Variable name: `ANTHROPIC_API_KEY`
    
    Variable value: `[Enter your Anthropic API Key]`
    
    Click 'OK'
    
    Click 'OK'
    
4.  Open `Clipalyst.exe`
   
    You're all set!
## Method 2
1.  **Clone the repository:**
    ```bash
    git clone https://github.com/LilWeenieZ/Clipalyst.git
    cd Clipalyst
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Setup environment variables:**
    Create a `.env` file in the root directory and add your API key:
    ```env
    ANTHROPIC_API_KEY=your_sk_key_here
    ```

4.  **Run the application:**
    ```bash
    python -m src.main
    ```

## 🛠️ Build

To generate a standalone Windows executable:
```bash
python build.py
```
The output will be in the `release/` directory.

## 🔒 Security & Privacy

- **Local Storage**: All history is stored in `data/clipboard.db`.
- **Ignore List**: Configure Clipalyst to ignore sensitive applications in the Settings.
- **AI Safety**: Secret detection patterns run locally before any content is sent to AI models.

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---
> *"The best clipboard manager is the one you never have to think about."*
