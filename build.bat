@echo off
echo Building Backup Manager Executable...
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --noconfirm --onedir --windowed --name "BackupManager" main.py
echo Build complete! Check the dist folder.
pause
