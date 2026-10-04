@echo off
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 exit /b 1
.venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
.venv\Scripts\python -m PyInstaller --noconfirm --clean --onefile --windowed --name IDLAPS-Triathlon main.py
if errorlevel 1 exit /b 1
echo Selesai. File ada di dist\IDLAPS-Triathlon.exe
pause
