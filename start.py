import subprocess
import sys
import os

# Always run using the venv Python if available
VENV_PYTHON = os.path.join(os.path.dirname(__file__), "venv", "Scripts", "python.exe")
PYTHON = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable

APP_PATH = os.path.join(os.path.dirname(__file__), "backend", "app.py")

print("==========================================")
print("   SMART STUDY AI ASSISTANT - STARTING   ")
print("==========================================")
print(f"Using Python : {PYTHON}")
print(f"App          : {APP_PATH}")
print("Server URL   : http://127.0.0.1:5000")
print("Press CTRL+C to stop.")
print("==========================================\n")

subprocess.run([PYTHON, APP_PATH])
