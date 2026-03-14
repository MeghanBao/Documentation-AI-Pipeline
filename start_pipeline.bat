@echo off
chcp 65001 >nul
title Dokumenten-KI Pipeline — Lokaler Betrieb

echo.
echo  =============================================
echo   Dokumenten-KI Pipeline  ^|  Start
echo  =============================================
echo.

REM -------------------------------------------------------
REM  Ins Projektverzeichnis wechseln (egal wo doppelgeklickt)
REM -------------------------------------------------------
cd /d "%~dp0"

REM -------------------------------------------------------
REM  1. Python prüfen
REM -------------------------------------------------------
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo  ┌─────────────────────────────────────────────────┐
    echo  │  FEHLER: Python wurde nicht gefunden.           │
    echo  └─────────────────────────────────────────────────┘
    echo.
    echo  Python 3.10 oder neuer wird benoetigt.
    echo.
    echo  So installieren Sie Python:
    echo    1. Oeffnen Sie:  https://www.python.org/downloads/
    echo    2. Laden Sie die neueste Version herunter.
    echo    3. Starten Sie den Installer und aktivieren Sie
    echo       "Add Python to PATH" ganz unten im Fenster.
    echo    4. Starten Sie danach dieses Skript erneut.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PYTHON_VER=%%v
echo  ✓ %PYTHON_VER% gefunden.

REM -------------------------------------------------------
REM  2. doc_pipeline-Paket prüfen
REM -------------------------------------------------------
python -c "import doc_pipeline" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo.
    echo  ┌─────────────────────────────────────────────────┐
    echo  │  FEHLER: Pipeline-Paket nicht installiert.      │
    echo  └─────────────────────────────────────────────────┘
    echo.
    echo  Bitte einmalig in diesem Ordner ausfuehren:
    echo.
    echo    pip install -e .
    echo.
    pause
    exit /b 1
)
echo  ✓ Pipeline-Paket gefunden.

REM -------------------------------------------------------
REM  3. Tesseract prüfen (PATH + Standard-Windows-Pfad)
REM -------------------------------------------------------
set TESS_OK=0
where tesseract >nul 2>&1
if %ERRORLEVEL% equ 0 set TESS_OK=1
if "%TESS_OK%"=="0" (
    if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" set TESS_OK=1
)

if "%TESS_OK%"=="1" (
    echo  ✓ Tesseract OCR gefunden.
) else (
    echo.
    echo  ┌─────────────────────────────────────────────────┐
    echo  │  HINWEIS: Tesseract OCR nicht gefunden.         │
    echo  │                                                 │
    echo  │  Gescannte Dokumente koennen nicht per OCR      │
    echo  │  verarbeitet werden. Nur PDFs mit eingebettetem │
    echo  │  Text funktionieren.                            │
    echo  └─────────────────────────────────────────────────┘
    echo.
    echo  Tesseract installieren (empfohlen):
    echo    https://github.com/UB-Mannheim/tesseract/wiki
    echo    (Installer ausfuehren, bei Sprachpaketen "German" auswaehlen)
    echo.
    echo  Die Pipeline startet jetzt trotzdem weiter...
    timeout /t 6 >nul
)

REM -------------------------------------------------------
REM  4. Doppelstart verhindern
REM -------------------------------------------------------
tasklist /FI "WINDOWTITLE eq DOC_PIPELINE_WATCHER*" 2>nul | find "cmd.exe" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo.
    echo  [HINWEIS] Die Pipeline laeuft bereits.
    echo  Browser wird geoeffnet...
    timeout /t 2 >nul
    start http://localhost:8501
    echo.
    pause
    exit /b 0
)

REM -------------------------------------------------------
REM  5. Datenordner festlegen und anlegen
REM -------------------------------------------------------
if not defined PIPELINE_BASE_DIR set "PIPELINE_BASE_DIR=%~dp0data\_pipeline"

if not exist "%PIPELINE_BASE_DIR%" (
    echo.
    echo  Erstelle Datenordner: %PIPELINE_BASE_DIR%
    mkdir "%PIPELINE_BASE_DIR%"
    echo  ✓ Datenordner erstellt.
)

if not exist "%~dp0logs" mkdir "%~dp0logs"

echo.
echo  Datenordner:  %PIPELINE_BASE_DIR%
echo.

REM -------------------------------------------------------
REM  6. Dateiüberwachung (Watcher) starten
REM -------------------------------------------------------
echo  Starte Dateiueberwachung...
start "DOC_PIPELINE_WATCHER" /min cmd /c ^
    "python -m doc_pipeline --base-dir "%PIPELINE_BASE_DIR%" >> "%~dp0logs\watcher.log" 2>&1"
echo  ✓ Dateiueberwachung laeuft im Hintergrund.

REM -------------------------------------------------------
REM  7. Streamlit Web-Oberfläche starten
REM -------------------------------------------------------
echo  Starte Web-Oberflaeche...
start "DOC_PIPELINE_UI" /min cmd /c ^
    "python -m streamlit run "%~dp0src\doc_pipeline\ui.py" --server.port=8501 --server.address=localhost --server.headless=true --browser.gatherUsageStats=false >> "%~dp0logs\ui.log" 2>&1"

REM -------------------------------------------------------
REM  8. Warten bis Streamlit hochgefahren ist, dann Browser öffnen
REM -------------------------------------------------------
echo  Warte auf Web-Oberflaeche (ca. 5 Sekunden)...
timeout /t 5 >nul

start http://localhost:8501

echo.
echo  =============================================
echo   Pipeline laeuft!
echo.
echo   Web-Oberflaeche:  http://localhost:8501
echo.
echo   Dokumente ablegen in:
echo   %PIPELINE_BASE_DIR%\input_manual\
echo.
echo   Protokolldateien:  logs\watcher.log
echo                      logs\ui.log
echo.
echo   Zum Beenden: beliebige Taste druecken
echo   ODER stop_pipeline.bat doppelklicken
echo  =============================================
echo.
pause >nul

REM -------------------------------------------------------
REM  9. Aufräumen beim Beenden
REM -------------------------------------------------------
echo.
echo  Beende Pipeline — bitte warten...
call :cleanup
echo.
echo  ✓ Pipeline gestoppt. Auf Wiedersehen!
timeout /t 2 >nul
exit /b 0

REM -------------------------------------------------------
:cleanup
REM -------------------------------------------------------
taskkill /FI "WINDOWTITLE eq DOC_PIPELINE_WATCHER*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq DOC_PIPELINE_UI*" /F >nul 2>&1
wmic process where "commandline like '%%doc_pipeline%%' and name='python.exe'" delete >nul 2>&1
wmic process where "commandline like '%%streamlit%%' and name='python.exe'" delete >nul 2>&1
exit /b 0
