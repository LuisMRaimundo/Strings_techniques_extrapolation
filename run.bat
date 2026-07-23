@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title String Technique Density Model

where python >nul 2>&1
if errorlevel 1 (
  echo Python was not found on PATH.
  echo Install Python 3.10+ and try again.
  pause
  exit /b 1
)

echo Installing / updating dependencies...
python -m pip install -e ".[dev]" -q
if errorlevel 1 (
  echo.
  echo Dependency install failed. Trying requirements-free editable install...
  python -m pip install -e . -q
  if errorlevel 1 (
    echo Install failed.
    pause
    exit /b 1
  )
)

echo.
echo Launching GUI...
python -m string_technique_model.gui
if errorlevel 1 (
  echo.
  echo GUI exited with an error.
  pause
  exit /b 1
)

endlocal
