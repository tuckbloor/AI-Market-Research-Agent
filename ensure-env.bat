@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Create this project's private Python environment automatically if needed.
if exist ".venv\Scripts\python.exe" goto dependencies

echo [SETUP] Python environment not found. Creating .venv automatically...
where py >nul 2>&1
if errorlevel 1 goto python_fallback

py -3.14 --version >nul 2>&1
if errorlevel 1 goto try_any_launcher
py -3.14 -m venv ".venv"
if exist ".venv\Scripts\python.exe" goto dependencies

:try_any_launcher
py -3 --version >nul 2>&1
if errorlevel 1 goto python_fallback
py -3 -m venv ".venv"
if exist ".venv\Scripts\python.exe" goto dependencies

:python_fallback
where python >nul 2>&1
if errorlevel 1 goto missing_python
python -m venv ".venv"
if exist ".venv\Scripts\python.exe" goto dependencies

goto environment_failed

:dependencies
rem An existing environment should not reinstall packages on every launch.
if /i "%~1"=="test" goto test_dependencies
".venv\Scripts\python.exe" -c "import streamlit, requests, bs4" >nul 2>&1
if not errorlevel 1 goto success
set "REQUIREMENTS=requirements.txt"
goto install_dependencies

:test_dependencies
".venv\Scripts\python.exe" -c "import streamlit, requests, bs4, pytest" >nul 2>&1
if not errorlevel 1 goto success
set "REQUIREMENTS=requirements-dev.txt"

:install_dependencies
echo [SETUP] Installing missing Python packages from %REQUIREMENTS% ...
".venv\Scripts\python.exe" -m pip install -r "%REQUIREMENTS%"
if errorlevel 1 goto dependency_failed
if /i "%~1"=="test" goto verify_test
".venv\Scripts\python.exe" -c "import streamlit, requests, bs4" >nul 2>&1
if errorlevel 1 goto dependency_failed
goto success

:verify_test
".venv\Scripts\python.exe" -c "import streamlit, requests, bs4, pytest" >nul 2>&1
if errorlevel 1 goto dependency_failed

goto success

:success
endlocal & exit /b 0

:missing_python
echo [ERROR] No usable Python installation was found.
echo Install Python 3.14 or 3.13 and ensure the Python launcher is available.
endlocal & exit /b 1

:environment_failed
echo [ERROR] Could not create .venv. Check Python installation and folder permissions.
endlocal & exit /b 1

:dependency_failed
echo [ERROR] Python package installation failed. Check the messages above.
echo You may need internet access and a compatible Python installation.
endlocal & exit /b 1
