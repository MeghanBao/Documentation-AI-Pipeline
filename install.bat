@echo off
chcp 65001 >nul
title Dokumenten-KI Pipeline — Einrichtung

echo.
echo  =============================================
echo   Dokumenten-KI Pipeline  ^|  Einrichtung
echo  =============================================
echo.

REM -------------------------------------------------------
REM  1. Docker Desktop prüfen
REM -------------------------------------------------------
where docker >nul 2>&1
if %ERRORLEVEL% neq 0 goto :docker_not_found

REM -------------------------------------------------------
REM  2. Docker-Daemon läuft?  Falls nicht → starten
REM -------------------------------------------------------
docker info >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo  Docker Desktop wurde gefunden, ist aber noch nicht gestartet.
    echo  Starte Docker Desktop automatisch...
    echo.
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe" >nul 2>&1

    echo  Bitte warten, bis Docker Desktop hochgefahren ist.
    echo  Das kann bis zu 60 Sekunden dauern...
    echo.

    REM  Warte bis zu 60 s in 5-s-Schritten
    set /a RETRIES=12
    :wait_loop
    timeout /t 5 >nul
    docker info >nul 2>&1
    if %ERRORLEVEL% equ 0 goto :docker_ready
    set /a RETRIES-=1
    if %RETRIES% gtr 0 goto :wait_loop

    echo  [FEHLER] Docker Desktop hat sich nicht rechtzeitig gemeldet.
    echo  Bitte Docker Desktop manuell starten und danach install.bat erneut ausführen.
    echo.
    pause
    exit /b 1
)

:docker_ready
echo  ✓ Docker Desktop ist bereit.
echo.

REM -------------------------------------------------------
REM  3. Datenordner anlegen (einmalig beim ersten Start)
REM -------------------------------------------------------
if not exist "data\_pipeline" (
    echo  Erstelle Datenordner  data\_pipeline\ ...
    mkdir "data\_pipeline"
    echo  ✓ Datenordner erstellt.
    echo.
)

REM -------------------------------------------------------
REM  4. Container bauen und starten
REM -------------------------------------------------------
echo  Baue und starte Pipeline-Container...
echo  (Beim allerersten Start wird das Docker-Image gebaut.
echo   Das kann 5–15 Minuten dauern — bitte warten.)
echo.

docker compose up --build -d
if %ERRORLEVEL% neq 0 (
    echo.
    echo  [FEHLER] Der Container konnte nicht gestartet werden.
    echo  Bitte die Fehlermeldung oben lesen.
    echo  Häufige Ursachen:
    echo    - Port 8501 ist bereits belegt  →  anderen Port in docker-compose.yml setzen
    echo    - Unzureichender Arbeitsspeicher  →  Docker Desktop RAM erhöhen
    echo.
    pause
    exit /b 1
)

REM -------------------------------------------------------
REM  5. Browser öffnen
REM -------------------------------------------------------
echo.
echo  ✓ Pipeline läuft erfolgreich!
echo  Öffne Browser auf http://localhost:8501 ...
timeout /t 3 >nul
start http://localhost:8501

echo.
echo  =============================================
echo   Installation abgeschlossen!
echo.
echo   Web-Oberfläche:  http://localhost:8501
echo.
echo   Container stoppen:   docker compose down
echo   Container starten:   start.bat  (für den täglichen Betrieb)
echo  =============================================
echo.
pause
exit /b 0

REM -------------------------------------------------------
:docker_not_found
REM -------------------------------------------------------
echo  ┌─────────────────────────────────────────────────┐
echo  │  Docker Desktop ist nicht installiert.          │
echo  │                                                 │
echo  │  Docker Desktop wird benötigt, um die           │
echo  │  Dokumenten-KI Pipeline auszuführen.            │
echo  └─────────────────────────────────────────────────┘
echo.
echo  So installieren Sie Docker Desktop:
echo.
echo    1. Öffnen Sie die Download-Seite (wird gleich automatisch geöffnet):
echo       https://www.docker.com/products/docker-desktop/
echo.
echo    2. Laden Sie "Docker Desktop for Windows" herunter und führen
echo       Sie den Installer aus.
echo.
echo    3. Starten Sie den Computer ggf. neu (vom Installer angezeigt).
echo.
echo    4. Starten Sie Docker Desktop und warten Sie, bis es bereit ist
echo       (Taskleiste: Docker-Symbol erscheint).
echo.
echo    5. Führen Sie diese Datei (install.bat) erneut aus.
echo.
echo  Öffne Browser für den Download...
timeout /t 2 >nul
start https://www.docker.com/products/docker-desktop/
echo.
pause
exit /b 1
