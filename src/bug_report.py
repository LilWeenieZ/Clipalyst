import webbrowser
import platform
import urllib.parse

# Import VERSION from main inside the function to avoid circular imports
# main -> settings_window -> bug_report -> main
GITHUB_ISSUES_URL = "https://github.com/LilWeenieZ/Clipalyst/issues/new"

def open_bug_report():
    """Opens a pre-filled GitHub Issues URL in the default browser."""
    from src.main import VERSION
    
    os_ver = platform.version()
    
    body_template = (
        "### Describe the bug\n"
        "\n"
        "\n"
        "### Steps to reproduce\n"
        "1. \n"
        "2. \n"
        "\n"
        "### Environment\n"
        f"- OS: Windows {os_ver}\n"
        f"- Clipalyst Version: {VERSION}\n"
    )
    
    params = {
        "body": body_template,
        "title": "[Bug] "
    }
    
    query_string = urllib.parse.urlencode(params)
    url = f"{GITHUB_ISSUES_URL}?{query_string}"
    
    webbrowser.open(url)
