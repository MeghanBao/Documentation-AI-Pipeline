# Bedienungsanleitung – Dokumenten-KI Pipeline

> Für nicht-technische Nutzer. Kein Programmierwissen erforderlich.

---

## Was macht dieses Programm?

Das Programm liest Ihre eingescannten Dokumente automatisch ein, erkennt den Inhalt (z. B. „Rechnung", „Versicherung", „Lohnabrechnung"), liest das Datum aus dem Dokument und legt die Datei mit einem sinnvollen Namen im richtigen Ordner ab.

**Beispiel:**

```
scan_001.pdf   →   2025-02-18_Rechnung_Strom.pdf
                   (abgelegt in archiv/Rechnungen/)
```

Alles läuft **lokal auf Ihrem Computer** — keine Cloud, keine Internetverbindung notwendig.

---

## Voraussetzung: Docker Desktop installieren

Das Programm läuft in einem sogenannten „Container". Dafür wird einmalig **Docker Desktop** benötigt.

1. Öffnen Sie: **https://www.docker.com/products/docker-desktop/**
2. Laden Sie die Windows-Version herunter und installieren Sie sie
3. Starten Sie Docker Desktop und warten Sie, bis das Symbol in der Taskleiste grün leuchtet

> ✅ Docker Desktop muss im Hintergrund laufen, bevor Sie die Pipeline starten.

---

## Schritt 1: Pipeline starten

1. Öffnen Sie den Projektordner `Documentation-AI-Pipeline`
2. Doppelklicken Sie auf **`start.bat`**

```
[start.bat doppelklicken]
        │
        ▼
  Schwarzes Fenster öffnet sich
  (beim ersten Start: Bitte warten, Image wird gebaut ~2–5 Min.)
        │
        ▼
  Browser öffnet sich automatisch
  → http://localhost:8501
```

> ℹ️ Beim **allerersten Start** dauert es 2–5 Minuten, weil das Programm
> einmalig eingerichtet wird. Danach startet es in Sekunden.

---

## Schritt 2: Dokument einreichen

Sie haben **zwei Möglichkeiten**:

### Variante A — Über die Web-Oberfläche hochladen (empfohlen)

1. Öffnen Sie den Browser auf **http://localhost:8501**
2. Klicken Sie auf den Tab **📤 Hochladen & Verarbeiten**
3. Ziehen Sie Ihre PDF-Datei in das gestrichelte Feld,
   oder klicken Sie auf **Browse files** und wählen Sie die Datei aus

```
┌─────────────────────────────────────────┐
│                                         │
│   Datei hierher ziehen                  │
│         oder                            │
│   [ Browse files ]                      │
│                                         │
└─────────────────────────────────────────┘
```

4. Klicken Sie auf **▶ Verarbeiten**
5. Das Ergebnis erscheint sofort:

| Symbol | Bedeutung |
|--------|-----------|
| ✅ grün | Dokument erkannt und archiviert |
| ⚠️ gelb | Datum oder Typ unsicher → bitte manuell prüfen |
| 🔴 rot  | Datei konnte nicht gelesen werden (beschädigt?) |

---

### Variante B — Scanner (automatisch)

Wenn Ihr Scanner ins Netzwerk-Laufwerk `N:\` scannt:

1. Stellen Sie das Scan-Ziel Ihres Scanners auf:
   ```
   N:\_pipeline\input_scanner\
   ```
2. Scannen Sie das Dokument wie gewohnt
3. Die Pipeline erkennt die neue Datei **automatisch** und verarbeitet sie

> ℹ️ Keine weitere Aktion notwendig — der Watcher läuft im Hintergrund.

---

## Schritt 3: Ergebnis im Archiv prüfen

1. Klicken Sie auf den Tab **📁 Archiv**
2. Sie sehen alle Dokumente, nach Kategorie geordnet:

```
📁 Rechnungen      (3 Dateien)
   2025-02-18_Rechnung_Strom.pdf
   2025-01-05_Rechnung_Internet.pdf
   ...

📁 Versicherung    (1 Datei)
   2024-11-03_Versicherung_Haftpflicht.pdf

📁 Steuer          (0 Dateien)
📁 Arbeit          (0 Dateien)
📁 Verträge        (0 Dateien)
📁 Sonstiges       (0 Dateien)
```

Klicken Sie auf **↻ Neu laden**, um die Ansicht zu aktualisieren.

---

## Ordner auf dem Computer / NAS

Die Dateien befinden sich im Unterordner `data\_pipeline\` des Programmordners:

| Ordner | Inhalt |
|--------|--------|
| `input_scanner\` | Scans vom Scanner (werden automatisch verarbeitet) |
| `input_manual\` | Manuell abgelegte Dateien |
| `archiv\Rechnungen\` | Fertig archivierte Rechnungen |
| `archiv\Versicherung\` | Fertig archivierte Versicherungsdokumente |
| `archiv\Steuer\` | Steuerbescheide, Steuererklärungen |
| `archiv\Arbeit\` | Lohnabrechnungen |
| `archiv\Verträge\` | Verträge |
| `archiv\Sonstiges\` | Sonstiges |
| `review\` | ⚠️ Unsichere Dokumente — bitte manuell prüfen |
| `input_error\` | 🔴 Fehlerhafte Dateien (beschädigt / nicht lesbar) |

---

## Pipeline beenden

Um die Pipeline zu stoppen, öffnen Sie ein Eingabeaufforderungsfenster im
Programmordner und geben Sie ein:

```
docker compose down
```

Oder starten Sie einfach den Computer neu — Docker Desktop beendet die Container automatisch.

---

## Häufige Fragen

**Das Programm startet nicht.**
→ Ist Docker Desktop geöffnet und das Symbol in der Taskleiste grün? Warten Sie, bis Docker vollständig geladen ist, und starten Sie `start.bat` erneut.

**Beim ersten Start passiert lange nichts.**
→ Beim allerersten Mal wird das Programm eingerichtet. Bitte 2–5 Minuten Geduld. Das schwarze Fenster zeigt den Fortschritt.

**Ein Dokument liegt im `review/` Ordner.**
→ Das Datum oder der Dokumenttyp konnte nicht eindeutig erkannt werden. Bitte öffnen Sie die Datei, prüfen Sie sie und verschieben Sie sie manuell in den richtigen Archivordner mit einem passenden Dateinamen.

**Eine Datei liegt im `input_error/` Ordner.**
→ Die Datei konnte nicht gelesen werden (z. B. beschädigte PDF). Versuchen Sie, die Datei erneut zu scannen.

**Der Browser zeigt „Diese Website ist nicht erreichbar".**
→ Die Pipeline läuft noch nicht. Bitte `start.bat` ausführen und warten, bis das schwarze Fenster „Pipeline läuft!" anzeigt.
