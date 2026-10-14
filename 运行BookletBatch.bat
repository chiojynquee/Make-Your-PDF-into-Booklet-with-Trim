@echo off
chcp 65001 >nul
set "SCRIPT_DIR=%~dp0"
where py >nul 2>&1
if %errorlevel% equ 0 (
    py -3 "%SCRIPT_DIR%BookletBatch.py"
) else (
    python "%SCRIPT_DIR%BookletBatch.py"
)
if errorlevel 1 (
    echo.
    echo 程序运行结束或发生错误。请查看上方提示。
)
pause
