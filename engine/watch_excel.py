"""
watch_excel.py
--------------
Watches the V8 Excel file for changes and auto-regenerates the JSON.
The Streamlit app detects the new JSON and reloads the cache automatically.

Usage:
    python watch_excel.py   (run in a separate terminal alongside Streamlit)
"""

import time
import traceback
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from excel_to_json import convert_excel_to_json, EXCEL_PATH

WATCH_FILE = EXCEL_PATH.resolve()

# Debounce — Excel fires multiple events per save; ignore repeats within this window
DEBOUNCE_SECONDS = 2.0


class ExcelChangeHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self._last_triggered = 0.0

    def on_modified(self, event):
        if Path(event.src_path).resolve() != WATCH_FILE:
            return

        now = time.time()
        if now - self._last_triggered < DEBOUNCE_SECONDS:
            return  # debounce duplicate events
        self._last_triggered = now

        print(f"\n📄 Change detected — regenerating JSON...")
        try:
            convert_excel_to_json()
            print("   Streamlit will reload on next browser refresh (press R).")
        except FileNotFoundError:
            # Excel briefly disappears during autosave
            print("⚠️  File temporarily unavailable — will retry on next save.")
        except Exception:
            print("❌ Rebuild failed:")
            traceback.print_exc()
            print("   Fix the issue in Excel and save again.")


if __name__ == "__main__":
    print(f"👀 Watching: {WATCH_FILE}")
    print("   Press Ctrl+C to stop.\n")

    handler = ExcelChangeHandler()
    observer = Observer()
    observer.schedule(handler, str(WATCH_FILE.parent), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopped.")
        observer.stop()

    observer.join()