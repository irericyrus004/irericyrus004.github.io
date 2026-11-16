@echo off
title PREPFIX Timetable Toolkit
cd /d "%~dp0"

rem keep the folder tidy: every "CHANGES - vNN.txt" lives in the CHANGES folder
if exist "CHANGES - *.txt" (
  if not exist "CHANGES\" mkdir "CHANGES"
  move /y "CHANGES - *.txt" "CHANGES\" >nul 2>nul
)

rem files from earlier versions (before the PREPFIX names) go to one folder you can delete
set "OLD=OLD FILES - safe to delete"
for %%F in ("Start Publisher.bat" "ireri_publisher.py" "ireri_core.py" "ireri_ui.py" "ireri_licence.py") do (
  if exist "%%~F" (
    if not exist "%OLD%\" mkdir "%OLD%"
    move /y "%%~F" "%OLD%\" >nul 2>nul
  )
)
if exist "__pycache__\" (
  if not exist "%OLD%\" mkdir "%OLD%"
  move /y "__pycache__" "%OLD%\__pycache__ %RANDOM%" >nul 2>nul
)
rem your settings folder: earlier versions called it publisher_data
if exist "publisher_data\" if not exist "prepfix_data\" ren "publisher_data" "prepfix_data" >nul 2>nul
rem the Excel / PDF reader is no longer used
if exist "sheet_reader.py" (
  if not exist "%OLD%\" mkdir "%OLD%"
  move /y "sheet_reader.py" "%OLD%\" >nul 2>nul
)
rem school copies made before: give the licence file its PREPFIX name
if exist "ireri-licence.json" if not exist "prepfix-licence.json" ren "ireri-licence.json" "prepfix-licence.json"
rem the PREPFIX logo icon: a shortcut in this folder and one on the desktop. Made again when the toolkit folder
rem was moved (it remembers where it was), so the icons always open THIS folder.
if not exist "prepfix_data\" mkdir "prepfix_data"
set "HERE=%~dp0"
set "WAS="
if exist "prepfix_data\desktop-icon.txt" set /p WAS=<"prepfix_data\desktop-icon.txt"
if /i not "%WAS%"=="%HERE%|icon3" (
  call :icon "%~dp0PREPFIX Timetable Toolkit.lnk"
  call :icon desktop
  >"prepfix_data\desktop-icon.txt" echo %HERE%^|icon3
)
if not exist "PREPFIX Timetable Toolkit.lnk" call :icon "%~dp0PREPFIX Timetable Toolkit.lnk"
set PYTHONDONTWRITEBYTECODE=1

rem ---- Python: use the one on this laptop; if there is none, PREPFIX installs it by itself (no admin needed) ----
set "PY="
set "PYW="
call :findpy
if not defined PY call :getpy
if not defined PY goto nopython

%PY% -c "import requests, bs4, openpyxl, pdfplumber, tkinter" >nul 2>nul
if errorlevel 1 (
  echo.
  echo  First run: setting up PREPFIX helpers, about 1 minute...
  echo.
  rem the helpers come inside this folder, so no internet is needed; the internet is only a second try
  if exist "%~dp0helpers\" %PY% -m pip install --user --disable-pip-version-check --no-index --find-links "%~dp0helpers" requests beautifulsoup4 openpyxl pdfplumber >nul 2>nul
  %PY% -c "import requests, bs4, openpyxl, pdfplumber" >nul 2>nul
  if errorlevel 1 %PY% -m pip install --user --disable-pip-version-check --upgrade requests beautifulsoup4 openpyxl pdfplumber
  %PY% -c "import requests, bs4, openpyxl, pdfplumber, tkinter" >nul 2>nul
  if errorlevel 1 (
    echo.
    echo  Could not finish setting up. Connect to the internet and double-click Start PREPFIX.bat again.
    echo  Still stuck? Call Cyrus Ireri, 0720872582.
    pause
    exit /b 1
  )
)

start "" "%PYW%" "%~dp0prepfix_timetable.py"
exit /b 0

:icon
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p='%~1'; if($p -eq 'desktop'){$p=Join-Path ([Environment]::GetFolderPath('Desktop')) 'PREPFIX Timetable Toolkit.lnk'}; $s=(New-Object -ComObject WScript.Shell).CreateShortcut($p); $s.TargetPath='%~dp0Start PREPFIX.bat'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%~dp0teacher_app\brand\prepfix-toolkit.ico,0'; $s.WindowStyle=7; $s.Description='PREPFIX Timetable Toolkit'; $s.Save()" >nul 2>nul
exit /b 0

:findpy
rem a Python that really runs (Windows 10/11 has a fake "python" that only opens the Microsoft Store: skipped)
set "PY="
set "PYW="
set "PYEXE="
for %%C in ("py -3" "python") do if not defined PYEXE (
  %%~C -c "import sys, tkinter; print(sys.executable)" >"%TEMP%\prepfix-py.txt" 2>nul && set /p PYEXE=<"%TEMP%\prepfix-py.txt"
)
if not defined PYEXE for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*" "%ProgramFiles%\Python3*") do (
  if exist "%%~D\python.exe" "%%~D\python.exe" -c "import tkinter" >nul 2>nul && set "PYEXE=%%~D\python.exe"
)
del "%TEMP%\prepfix-py.txt" >nul 2>nul
if not defined PYEXE exit /b 0
set "PY="%PYEXE%""
set "PYW=%PYEXE:python.exe=pythonw.exe%"
if not exist "%PYW%" set "PYW=%PYEXE%"
exit /b 0

:getpy
echo.
echo  This laptop does not have Python yet. PREPFIX is installing it now.
echo  It needs the internet once (about 26 MB) and takes 2-5 minutes. Please wait...
echo.
set "PYSETUP=%~dp0helpers\python-setup.exe"
if not exist "%PYSETUP%" (
  set "PYSETUP=%TEMP%\prepfix-python-setup.exe"
  curl.exe -L -s -o "%TEMP%\prepfix-python-setup.exe" "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe" >nul 2>nul
  if not exist "%TEMP%\prepfix-python-setup.exe" powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol='Tls12'; Invoke-WebRequest 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile '%TEMP%\prepfix-python-setup.exe'" >nul 2>nul
)
if not exist "%PYSETUP%" exit /b 0
start "" /wait "%PYSETUP%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=0 Include_test=0 Include_doc=0 Include_tcltk=1 Include_pip=1
call :findpy
if defined PY echo  Python is ready.
exit /b 0

:nopython
echo.
echo  PREPFIX could not install Python by itself (no internet?). Connect to the internet and
echo  double-click "Start PREPFIX.bat" again. Or install it yourself:
echo.
echo  1. Go to https://www.python.org/downloads/ and download Python for Windows.
echo  2. When installing, TICK "Add python.exe to PATH", then click Install Now.
echo  3. Double-click "Start PREPFIX.bat" again.
echo.
start "" https://www.python.org/downloads/
pause
