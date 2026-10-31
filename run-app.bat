@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call "%~dp0ensure-env.bat" app
if errorlevel 1 goto startup_failed

echo.
echo [APP] Starting AI Market Research Agent...
echo [APP] Your browser should open automatically. If not, open http://localhost:8501
".venv\Scripts\python.exe" -m streamlit run app.py
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" echo [ERROR] The application exited with code %EXITCODE%.
echo.
pause
endlocal & exit /b %EXITCODE%

:startup_failed
echo.
echo [ERROR] Automatic Python setup failed. See details above.
pause
endlocal & exit /b 1
