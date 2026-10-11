"""回線チェッカー 取説ビューア / Connection Checker beginner's guide viewer

exe に埋め込んだ取説（HTML、日本語と英語）を一時フォルダに取り出して、既定のブラウザで開く。
言語は、アプリで選んだ言語（settings.json）に合わせる。選んでいなければ、Windows の表示言語に合わせる。
通信は一切しない。
"""

import ctypes
import json
import os
import shutil
import sys
import tempfile
import tkinter as tk
from tkinter import messagebox

GUIDES = {"ja": "回線チェッカー取説.html", "en": "Beginners_Guide_en.html"}


def resource_path(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def preferred_lang():
    try:
        path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "KaisenChecker", "settings.json")
        with open(path, encoding="utf-8") as f:
            lang = json.load(f).get("lang")
        if lang in GUIDES:
            return lang
    except (OSError, ValueError, AttributeError):
        pass
    try:
        # 下位 8 ビットが 0x11 なら日本語
        return "ja" if (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0xFF) == 0x11 else "en"
    except Exception:  # noqa: BLE001
        return "ja"


def main():
    lang = preferred_lang()
    try:
        dest_dir = os.path.join(tempfile.gettempdir(), "KaisenChecker_torisetsu")
        os.makedirs(dest_dir, exist_ok=True)
        for name in GUIDES.values():  # 言語の切り替えリンクが動くように、両方を取り出す
            shutil.copyfile(resource_path(name), os.path.join(dest_dir, name))
        os.startfile(os.path.join(dest_dir, GUIDES[lang]))
    except Exception as e:  # noqa: BLE001
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "回線チェッカー 取説 / Beginner's guide",
            f"取説を開けませんでした。 / Could not open the guide.\n\n{type(e).__name__}: {e}",
        )
        root.destroy()
        sys.exit(1)


if __name__ == "__main__":
    main()
