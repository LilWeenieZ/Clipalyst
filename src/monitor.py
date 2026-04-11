import threading
import time
import win32clipboard
import win32gui
import win32process
import win32api
import win32con
import os

class ClipboardMonitor:
    def __init__(self, db, ignore_list=None):
        self.db = db
        self.ignore_list = ignore_list if ignore_list is not None else []
        self.last_content = ""
        self._stop_event = threading.Event()
        self._thread = None
        
    def _get_active_process_name(self):
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    # Request permissions to query the process
                    h_process = win32api.OpenProcess(
                        win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, 
                        False, 
                        pid
                    )
                    if h_process:
                        exe_path = win32process.GetModuleFileNameEx(h_process, 0)
                        win32api.CloseHandle(h_process)
                        return os.path.basename(exe_path)
                except Exception:
                    # In case of insufficient permissions or no access to process (e.g. system processes)
                    pass
        except Exception:
            pass
        return "Unknown"
    
    def _read_clipboard(self):
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
                return data
            win32clipboard.CloseClipboard()
        except Exception:
            # If the clipboard is locked or an error occurs, make sure it is closed
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass
        return None

    def _monitor_loop(self):
        while not self._stop_event.is_set():
            content = self._read_clipboard()
            if content and isinstance(content, str):
                if content != self.last_content and len(content) >= 2:
                    self.last_content = content
                    source_app = self._get_active_process_name()
                    
                    # Check if source app is in ignore list
                    if source_app in self.ignore_list:
                        continue

                    if self.db:
                        # Depending on the DB implementation signature
                        # We pass content and source_app
                        self.db.insert_item(content, source_app=source_app)
            self._stop_event.wait(0.5)

    def start(self):
        """Starts the clipboard monitor in a background thread."""
        if not self.is_running():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._thread.start()

    def stop(self):
        """Stops the clipboard monitor."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def is_running(self):
        """Returns True if the monitor thread is active."""
        return self._thread is not None and self._thread.is_alive()

if __name__ == "__main__":
    import sys
    
    # Adjust path to import from src.database
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.database import ClipboardDB
    
    class TestDB(ClipboardDB):
        def insert_item(self, content, source_app=None):
            # Format and print the output as requested
            content_display = content[:30].replace('\n', ' ')
            print(f"Captured: {content_display} (from {source_app})")
            # Call original method to persist
            return super().insert_item(content, source_app)

    db = TestDB()
    monitor = ClipboardMonitor(db=db)
    
    print("Starting monitor for 30 seconds... (copy some text to see it captured)")
    monitor.start()
    
    try:
        time.sleep(30)
    except KeyboardInterrupt:
        pass
    finally:
        print("Time is up. Stopping monitor...")
        monitor.stop()
        print("Monitor stopped.")
