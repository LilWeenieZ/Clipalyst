import json
from pathlib import Path
from src.config import DATA_ROOT

class SettingsManager:
    DEFAULT_SETTINGS = {
        "history_limit": 1000,
        "auto_delete": "Never",
        "ignore_list": [],
        # Hotkey stored as individual components for easy UI binding
        "hotkey_ctrl":  True,
        "hotkey_shift": False,
        "hotkey_alt":   True,
        "hotkey_key":   "V",
        # AI model settings (Pro only)
        "ai_model":   "",   # empty = use default (claude-haiku-4-5)
        "ai_api_key": "",   # empty = use ANTHROPIC_API_KEY from .env
        # Licence
        "activation_key":   "",
        "activation_email": "",
        # Analytics
        "crash_reporting_enabled": True,
    }

    def __init__(self, settings_path=None):
        if settings_path is None:
            settings_path = DATA_ROOT / "settings.json"
        self.settings_path = Path(settings_path)
        self.settings = self.DEFAULT_SETTINGS.copy()
        self.listeners = []
        self.load()

    def add_listener(self, callback):
        self.listeners.append(callback)

    def _notify_listeners(self, key, value):
        for callback in self.listeners:
            try:
                callback(key, value)
            except Exception as e:
                print(f"Error in settings listener: {e}")

    def load(self):
        if self.settings_path.exists():
            try:
                with open(self.settings_path, "r") as f:
                    loaded_settings = json.load(f)
                    # Merge with defaults to handle missing keys in old files
                    self.settings.update(loaded_settings)
            except Exception as e:
                print(f"Error loading settings: {e}")
        else:
            self.save()

    def save(self):
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.settings_path, "w") as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        self.save()
        self._notify_listeners(key, value)
