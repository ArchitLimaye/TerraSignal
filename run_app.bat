@echo off
cd /d "%~dp0"
set "TERRASIGNAL_PYTHON=python"
if exist ".venv\Scripts\python.exe" set "TERRASIGNAL_PYTHON=.venv\Scripts\python.exe"
%TERRASIGNAL_PYTHON% -c "import flask, spacy, en_core_web_sm" >nul 2>&1
if errorlevel 1 (
  echo Project dependencies or the English NLP model are missing. Installing requirements...
  %TERRASIGNAL_PYTHON% -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Dependency installation failed. Check your Python and internet connection.
    pause
    exit /b 1
  )
)
%TERRASIGNAL_PYTHON% app.py
pause
