@echo off
rem Builds dist\wk1-converter.exe and dist\wk1-converter-gui.exe: a single file that needs no Python on the machine that runs it.
rem Needs Python 3.9 or newer on the machine that builds it. Everything it installs goes into .venv in this folder.
setlocal
cd /d "%~dp0"
if not exist .venv (
    python -m venv .venv || exit /b 1
)
call .venv\Scripts\python -m pip install --quiet --upgrade pip || exit /b 1
call .venv\Scripts\python -m pip install --quiet pyinstaller openpyxl || exit /b 1
call .venv\Scripts\python test_wk1.py || exit /b 1
call .venv\Scripts\python -m PyInstaller --onefile --console --name wk1-converter --clean --noconfirm wk1.py || exit /b 1
call .venv\Scripts\python -m PyInstaller --onefile --windowed --name wk1-converter-gui --noconfirm wk1.py || exit /b 1
echo.
echo Built dist\wk1-converter.exe (command line) and dist\wk1-converter-gui.exe (double-click, dialog boxes)
