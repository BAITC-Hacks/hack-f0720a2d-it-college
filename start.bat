@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
pushd "%~dp0" || exit /b 1

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" start.py %*
    goto finished
)
py -3.11 -c "import sys; assert sys.version_info[:2] == (3, 11)" >nul 2>&1
if not errorlevel 1 (
    py -3.11 start.py %*
    goto finished
)
python -c "import sys; assert sys.version_info[:2] == (3, 11)" >nul 2>&1
if not errorlevel 1 (
    python start.py %*
    goto finished
)
echo Python 3.11 is required. Install it, then double-click start.bat again.
echo See LOCAL_RUN.md for instructions.
popd
pause
exit /b 1

:finished
set "result=%errorlevel%"
popd
if not "%result%"=="0" (
    echo.
    echo Startup failed. See the message above and LOCAL_RUN.md.
    pause
)
exit /b %result%
