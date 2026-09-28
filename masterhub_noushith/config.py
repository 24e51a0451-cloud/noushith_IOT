"""
Global configuration for MasterHub
"""

# Chrome executable
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

# Change this whenever you want another profile
CHROME_PROFILE = "Profile 5"

# Chrome startup options
CHROME_ARGS = [
    f"--profile-directory={CHROME_PROFILE}"
]