"""回線チェッカー 取説ビューア

exe に埋め込んだ取説（HTML）を、一時フォルダに取り出して、既定のブラウザで開く。
通信は一切しない。
"""

import os
import shutil
import sys
import tempfile
import tkinter as tk
from tkinter import messagebox

HTML_NAME = "回線チェッカー取説.html"


def resource_path(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def main():
    src = resource_path(HTML_NAME)
    try:
        dest_dir = os.path.join(tempfile.gettempdir(), "KaisenChecker_torisetsu")
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, HTML_NAME)
        shutil.copyfile(src, dest)
        os.startfile(dest)
    except Exception as e:  # noqa: BLE001
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "回線チェッカー 取説",
            f"取説を開けませんでした。\n\n{type(e).__name__}: {e}",
        )
        root.destroy()
        sys.exit(1)


if __name__ == "__main__":
    main()
