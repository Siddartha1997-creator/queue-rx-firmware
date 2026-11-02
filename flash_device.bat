@echo off
REM ==============================================================================
REM QueueRX Windows Production Flasher
REM ==============================================================================
python "%~dp0flash_device.py" %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Flashing encountered an error.
    pause
)

