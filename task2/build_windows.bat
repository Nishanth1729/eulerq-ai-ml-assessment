@echo off
setlocal
cd /d "%~dp0"
set "PYTHON=C:\venvs\eulerq312\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo Python 3.12 environment not found at C:\venvs\eulerq312.
  echo Create it with: py -3.12 -m venv C:\venvs\eulerq312
  exit /b 1
)
rem The spec uses the system Tcl/Tk libraries when present and bundled scripts otherwise.
"%PYTHON%" -m PyInstaller --noconfirm --clean EulerQ_TextToSQL.spec --workpath build --distpath dist
if errorlevel 1 exit /b %errorlevel%
echo Built %~dp0dist\EulerQ_TextToSQL.exe
endlocal
