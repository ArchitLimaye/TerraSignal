@echo off
cd /d "%~dp0"
python -c "import flask" >nul 2>&1
if errorlevel 1 (
  echo Flask is missing. Installing project requirements...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Dependency installation failed. Check your Python and internet connection.
    pause
    exit /b 1
  )
)
python app.py
pause
