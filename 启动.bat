@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if not errorlevel 1 (
    py -3 -u jump.py %*
    goto finish
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if not errorlevel 1 (
    python -u jump.py %*
    goto finish
)
echo 未找到 Python 3.11 或更高版本。
echo 请安装 Python，并勾选 Add python.exe to PATH，然后重新双击本文件。
:finish
echo.
echo 程序已结束。可查看上面的提示或错误信息。
pause
endlocal
