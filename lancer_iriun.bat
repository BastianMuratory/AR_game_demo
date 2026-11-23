@echo off
rem Lance le tracker avec la camera Iriun du telephone.
rem Avant : appli Iriun Webcam ouverte sur le PC ET sur le telephone (meme Wi-Fi ou USB).
rem Options passees telles quelles au tracker, ex. : lancer_iriun.bat --camera 1
cd /d "%~dp0tracker"

where python >nul 2>nul
if errorlevel 1 (
  echo Python est introuvable. Installe-le depuis python.org en cochant "Add to PATH".
  pause
  exit /b 1
)

echo Verification des dependances...
python -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo L'installation des dependances a echoue.
  pause
  exit /b 1
)

if "%~1"=="" (
  python tracker.py --camera iriun
) else (
  python tracker.py %*
)
if errorlevel 1 pause
