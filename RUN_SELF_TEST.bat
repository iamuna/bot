@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" self_test.py
) else (
  where py.exe >nul 2>nul && (py -3 self_test.py) || (python self_test.py)
)
echo.
pause
