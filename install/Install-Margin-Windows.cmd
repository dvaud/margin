<# : Install Margin on Windows - double-click this file
@echo off
rem Margin @MARGIN_VERSION@: the one-line install for Windows as a file to double-click (since 0.14.5). It runs the
rem PowerShell part below, which is install.ps1 of the same release, so it does what the install line does: it gets
rem uv, downloads the Margin package and checks it, installs it, makes the Margin icon and opens Margin.
rem Windows may ask first, as for any program from the internet: click "More info", then "Run anyway".
rem To update Margin later, quit it and run the newest copy of this file. Your projects stay where they are.
rem
rem How it is made: tools/release.py puts install/install.ps1 below the last line of install/Install-Margin-Windows.cmd.
rem cmd runs the lines up to "exit /b" and stops there; PowerShell reads the whole file, in which everything up to the
rem end of the last line is a comment. So no line of this part may hold PowerShell's end of comment, and no rem line
rem a percent sign. Keep it plain ASCII; the release file gets Windows line endings.
setlocal
title Install Margin
set "MARGIN_SELF=%~f0"
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "Invoke-Expression ([IO.File]::ReadAllText($env:MARGIN_SELF))"
set "MARGIN_RC=%ERRORLEVEL%"
echo.
echo Press any key to close this window.
pause >nul
exit /b %MARGIN_RC%
: the PowerShell part, install.ps1, starts below this line #>
