@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 (
    python -m venv .venv
    if errorlevel 1 goto failed
  )
)
".venv\Scripts\python.exe" -c "import sys; print('Using Python', sys.version.split()[0]); sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
  echo Python 3.10 or newer is required. Check installed versions with: py --list
  goto failed
)
".venv\Scripts\python.exe" -m pip install -r requirements_demo.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" run_demo.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo If no Python runtime was found, run py --list to check your installed versions.
echo Demo did not start. Read SUBMISSION_README.md for setup and troubleshooting.
pause
exit /b 1
