import winreg
import sys

_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
_REG_NAME = "Clipalyst"

def test_startup():
    print(f"Testing access to {_REG_PATH} with name {_REG_NAME}")
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _REG_PATH,
            0,
            winreg.KEY_READ,
        )
        print("OpenKey succeeded")
        with key:
            try:
                value, type = winreg.QueryValueEx(key, _REG_NAME)
                print(f"QueryValueEx succeeded: {value} (type {type})")
            except FileNotFoundError:
                print("QueryValueEx failed: FileNotFoundError (value not found)")
    except Exception as e:
        print(f"Caught exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_startup()
