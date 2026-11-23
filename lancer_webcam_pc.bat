@echo off
rem Version WEBCAM DU PC : utilise la webcam integree / branchee (camera 0).
rem Si ce n'est pas la bonne : lancer_webcam_pc.bat --list-cameras, puis --camera <numero>.
rem Options passees telles quelles au tracker, ex. : lancer_webcam_pc.bat --camera 1
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

rem Si Godot est dans le PATH, on ouvre le jeu en meme temps (sinon : lance-le a la main, F5).
where godot >nul 2>nul
if not errorlevel 1 start "" godot --path "%~dp0godot"

if "%~1"=="" (
  python tracker.py --camera 0
) else (
  python tracker.py %*
)
if errorlevel 1 pause
