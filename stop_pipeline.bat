@echo off
chcp 65001 >nul
title Dokumenten-KI Pipeline — Stopp

echo.
echo  =============================================
echo   Dokumenten-KI Pipeline  ^|  Stopp
echo  =============================================
echo.
echo  Beende laufende Pipeline-Prozesse...
echo.

REM -------------------------------------------------------
REM  Dateiüberwachung (Watcher) beenden
REM -------------------------------------------------------
set WATCHER_STOPPED=0
taskkill /FI "WINDOWTITLE eq DOC_PIPELINE_WATCHER*" /F >nul 2>&1
if %ERRORLEVEL% equ 0 set WATCHER_STOPPED=1
wmic process where "commandline like '%%doc_pipeline%%' and name='python.exe'" delete >nul 2>&1
if %ERRORLEVEL% equ 0 set WATCHER_STOPPED=1

if "%WATCHER_STOPPED%"=="1" (
    echo  ✓ Dateiueberwachung gestoppt.
) else (
    echo  - Dateiueberwachung war nicht aktiv.
)

REM -------------------------------------------------------
REM  Streamlit Web-Oberfläche beenden
REM -------------------------------------------------------
set UI_STOPPED=0
taskkill /FI "WINDOWTITLE eq DOC_PIPELINE_UI*" /F >nul 2>&1
if %ERRORLEVEL% equ 0 set UI_STOPPED=1
wmic process where "commandline like '%%streamlit%%' and name='python.exe'" delete >nul 2>&1
if %ERRORLEVEL% equ 0 set UI_STOPPED=1

if "%UI_STOPPED%"=="1" (
    echo  ✓ Web-Oberflaeche gestoppt.
) else (
    echo  - Web-Oberflaeche war nicht aktiv.
)

echo.
echo  =============================================
echo   Alle Pipeline-Prozesse wurden beendet.
echo.
echo   Zum erneuten Starten:
echo   start_pipeline.bat doppelklicken
echo  =============================================
echo.
pause
exit /b 0
