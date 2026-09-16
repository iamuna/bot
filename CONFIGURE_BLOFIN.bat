@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" setup_blofin.py
) else (
  where py.exe >nul 2>nul && (py -3 setup_blofin.py) || (python setup_blofin.py)
)
echo.
pause
