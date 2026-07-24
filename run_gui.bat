@echo off
setlocal
cd /d "%~dp0"
echo.
echo === Strings Techniques Extrapolation GUI ===
echo Code root: %CD%
echo.
python -m pip uninstall string-technique-model -y >nul 2>&1
python -m pip install -e "%CD%" --no-deps
if errorlevel 1 (
  echo pip install failed.
  pause
  exit /b 1
)
python -c "from string_technique_model.config import PACKAGE_ROOT; print('Import root:', PACKAGE_ROOT)"
echo.
echo Close any other STE windows first. Title bar must show this E: path.
echo.
python -m string_technique_model gui
endlocal
