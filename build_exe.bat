@echo off
REM Run this ON WINDOWS (PyInstaller can't cross-compile from Linux/Mac).
REM Produces dist\VoiceChanger.exe — a single-file app, no Python needed to run it.

python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller

pyinstaller --onefile --windowed --name VoiceChanger app.py

echo.
echo Done. Your exe is at dist\VoiceChanger.exe
pause
