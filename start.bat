@echo off
chcp 65001 >nul
title Dokumenten-KI Pipeline

echo.
echo  =============================================
echo   Dokumenten-KI Pipeline  ^|  Start
echo  =============================================
echo.

REM --- Docker prüfen ---
where docker >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo  [FEHLER] Docker Desktop wurde nicht gefunden.
    echo.
    echo  Bitte zuerst Docker Desktop installieren:
    echo  https://www.docker.com/products/docker-desktop/
    echo.
    pause
    exit /b 1
)

REM --- Docker Desktop läuft? ---
docker info >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo  [FEHLER] Docker Desktop ist nicht gestartet.
    echo.
    echo  Bitte Docker Desktop öffnen und warten bis es bereit ist,
    echo  dann dieses Fenster erneut starten.
    echo.
    pause
    exit /b 1
)

REM --- Datenordner anlegen (beim ersten Start) ---
if not exist "data\_pipeline" (
    echo  Erstelle Datenordner...
    mkdir "data\_pipeline"
)

REM --- Container starten ---
echo  Starte Pipeline-Container...
echo  (Beim ersten Start wird das Image gebaut — das kann einige Minuten dauern.)
echo.
docker compose up --build -d

if %ERRORLEVEL% neq 0 (
    echo.
    echo  [FEHLER] Container konnte nicht gestartet werden.
    echo  Fehlermeldung bitte oben ablesen.
    echo.
    pause
    exit /b 1
)

REM --- Browser öffnen ---
echo.
echo  Pipeline läuft!  Öffne Browser...
timeout /t 3 >nul
start http://localhost:8501

echo.
echo  =============================================
echo   Web-Oberfläche:  http://localhost:8501
echo.
echo   Zum Beenden in diesem Fenster:
echo     docker compose down
echo  =============================================
echo.
pause
