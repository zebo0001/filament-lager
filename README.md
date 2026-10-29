# The Filament Storage System

*Deutsch | [English](README.en.md)*

Eigenstaendiges Lagerverwaltungs-System fuer 3D-Druck-Filament: [Spoolman](https://github.com/Donkie/Spoolman) fuer die Spulenverwaltung, plus ein eigenes Lagerplatz-Modul, das Spulen konkreten physischen Plaetzen (Drucker, ACE-Einheit, Drybox, ...) zuordnet - inklusive Drag & Drop, Einkaufsliste bei leeren Rollen, visueller Lager-Ansicht, einem eigenen Label-Designer fuer Etiketten (mit QR/Barcode-Export als PNG/PDF) und einem scan-gestuetzten Workflow fuer Wareneingang und Lagerplatz-Zuordnung (Hardware-Scanner oder Handykamera).

Laeuft bei uns produktiv seit mehreren Wochen. Ruerckmeldungen, Bugs und Verbesserungsvorschlaege sind sehr willkommen - gerne als Issue in diesem Repo.

## Screenshot

![Lagerplaetze-Ansicht](docs/dashboard-screenshot.png)

## Voraussetzungen

- Docker Desktop (Windows/Mac) oder Docker + Compose-Plugin (Linux)
- Der `storage`-Dienst baut auf einem Playwright/Chromium-Basisimage auf (fuer den Label-PNG/PDF-Export) - das Image ist entsprechend groesser, der erste `docker compose up -d` dauert daher beim Bauen etwas laenger als bei einem schlanken Python-Image.

## Starten

```bash
docker compose up -d
```

Danach:

- Dashboard: http://localhost:8093
- Spoolman (vollstaendige Oberflaeche): http://localhost:8091

Ports lassen sich ueber eine `.env`-Datei anpassen (Vorlage: `.env.example`).

**Wichtig fuer den Kamera-Scan:** Kamera-basiertes QR-Scannen (im Scan-Modus, als Alternative zu einem Hardware-Scanner) braucht laut Browser-Vorgabe einen sicheren Kontext (HTTPS oder `localhost`). Ueber `http://localhost:8093` auf demselben Rechner funktioniert das direkt. Greift man vom Handy aus ueber die LAN-IP des Docker-Hosts zu (z.B. `http://192.168.x.x:8093`), ist die Kamera-Option automatisch deaktiviert (mit Hinweistext) - dann bleibt nur ein externer Hardware-Barcode-/QR-Scanner (HID-Tastatur-Emulation) als Eingabeweg, oder man stellt den Dashboard-Zugriff selbst per Reverse-Proxy auf HTTPS um.

## Was ist zu testen?

Grundfunktionen:

- Spulen in Spoolman anlegen (Material, Hersteller, Farbe, auch mehrfarbig), inkl. Artikelnummer-Feld
- Geraete im Geraete-Wizard anlegen (Dashboard -> Lagerplaetze -> Geraete-Wizard): Drucker (optional mit ACE/AMS-Zufuehrung) oder Drybox - mit Live-Vorschau waehrend der Eingabe. Alle Geraetetypen laufen durch denselben Wizard, kein separates Formular mehr noetig
- Verschachtelte Geraete: ein Drucker mit ACE/AMS kann mehrere Zufuehrungs-Boxen als eigene Untergeraete enthalten. Die Lagerplaetze-Uebersicht stellt das eingerueckt dar
- Spulen per Drag & Drop bzw. Zuweisungsdialog ('Auf Drucker/ACE', 'In Drybox') auf Plaetze legen
- Auf einen Spulennamen in der Tabelle klicken -> Detail-/Edit-Modal oeffnet sich (Preis, Gewichte, Lot-Nr., Kommentar, Temperatur-Overrides, Filament-Typ-Felder) - auch nachtraegliche Bearbeitung moeglich
- 'Rolle leer' testen (archiviert die Spule in Spoolman, gibt den Platz frei, setzt einen Eintrag auf die Einkaufsliste inkl. Artikelnummer)
- Suche und Pagination im Spulenverzeichnis
- Panel-Reihenfolge im Dashboard ueber den Einstellungen-Button anpassen

Label-Designer (eigener Menuepunkt im Dashboard):

- Eigene Etikettenvorlagen per Drag & Drop zusammenstellen (Text mit Spoolman-Variablen wie Name/Material/Hersteller/Farbe, Spulen-Icon, Farbfeld, Barcode/QR-Code)
- Vorlagen sind nach Spule oder Filament typisiert (Umschalter im Editor) - der QR-Code-Inhalt folgt dabei automatisch dem gewaehlten Typ
- Live-QR-Vorschau direkt im Design-Tab (kein Platzhalter mehr, echter QR-Code waehrend der Bearbeitung)
- Design- und Druck-Tab getrennt: im Druck-Tab lassen sich mehrere Spulen/Filamente fuer einen Etikettenbogen (Sheet-Tile-Druck) auswaehlen, inkl. Live-Vorschau des Bogens
- QR-Code enthaelt automatisch das App-Logo im Zentrum eingebettet
- QR-Inhalt folgt dem Schema `WEB+SPOOLMAN:S-<spool_id>` bzw. `WEB+SPOOLMAN:F-<filament_id>` (kompatibel zum Scan-Format des Spoolman-eigenen Label-Designers, Gross-/Kleinschreibung spielt beim Scannen keine Rolle)
- Vorlagen als PNG oder PDF exportieren (laeuft ueber Headless Chromium im `storage`-Dienst) und mit einem Etikettendrucker/Laserdrucker ausdrucken

Scan-gestuetzter Workflow (Hardware-Barcode-/QR-Scanner mit HID-Tastatur-Emulation, kein Treiber noetig - oder wahlweise die Handykamera, siehe HTTPS-Hinweis oben):

- Spulen-ID wird direkt in der Spulen-Tabelle angezeigt
- Slot-Label-Generierung und Druckansicht fuer Lagerplaetze
- Scan-Overlay mit Statusanzeige beim Scannen, Kamera-Scan optional per Toggle aktivierbar (Einstellung wird pro Geraet im Browser gespeichert)
- Vollstaendiger Scan-only Wareneingang: ein gescannter Filament-QR-Code legt automatisch eine neue Spule an, ein anschliessend gescannter Platz-Code weist sie direkt zu - ganz ohne manuelle Dialog-Interaktion
- Im 'Neue Spule'-Dialog kann alternativ ein gedrucktes Filament-QR-Label gescannt werden, um Material/Hersteller/Farbe automatisch vorzubefuellen

Drucker-Seite (eigener Menuepunkt im Dashboard, ab v1.4.0):

- Zeigt alle per Anycubic-Bridge verbundenen Drucker live (Status, aktuelles Druckprojekt, ACE-Slot-Belegung) zusammen mit manuell angelegten Platzhalter-Druckern in einer gemeinsamen Ansicht
- Laufende Drucke zeigen eine Spooly-artige Fortschrittskarte: Dateiname, grosse Prozentanzeige, Restzeit, geschaetzte Fertigstellungszeit, Fortschrittsbalken
- Idle-Drucker (status "available"/"online"/"standby") zeigen eine ruhige, nicht animierte Illustration statt der Druck-Animation
- Lagerplaetze lassen sich praezise mit einer einzelnen ACE-Box eines Druckers verknuepfen (nicht nur pauschal mit dem Drucker) - wichtig bei mehreren Zufuehrungs-Boxen am selben Geraet

Neu in v1.5.0 (Drucker-Seite und Historie):

- Jede Slot-Karte zeigt einen Spulenring in Filamentfarbe; die Fuellung entspricht der Restmenge laut Drucker, in der Mitte steht der Prozentwert. Der gerade eingezogene Slot ist farbig umrandet.
- Historie: 'Zuordnen' kann einen Druck auf zwei Spulen aufteilen (z.B. nach einem Spulenwechsel mitten im Druck); beim Spulenwechsel waehrend eines laufenden Drucks fragt das Dashboard nach.
- Anycubic-Bridge: Meldet ein Drucker (Kobra X) keinen aktiven Slot, wird der Slot ueber Farbe und Material bestimmt. Bei mehreren gleich aussehenden Spulen wird bewusst nicht automatisch gebucht.

Drucker-Seite, Live-Daten und Abgleich (v1.4.0):

- ACE-Boxen werden mit Farbe, Material und SKU angezeigt; der Slot, der gerade eingezogen ist, ist markiert. Der ACE-Anschluss am Geraet ist als 'ACE' beschriftet.
- Die Restmenge je Slot wird in Gramm angezeigt ('Drucker ca. 350 g - Spoolman 690 g'). Der Druckerwert ist eine Schaetzung (Restmenge in Prozent mal Startgewicht der zugeordneten Spule). Ab 15 Prozent Abweichung erscheint ein Warnhinweis.
- Direkt am Slot kann Verbrauch gebucht werden: Gramm eingeben und 'Buchen' oder 'Angleichen' (bucht die Differenz bis zum Druckerwert, nur wenn Spoolman mehr anzeigt). Beides fragt vorher nach. Waehrend ein Druck laeuft, besser nicht angleichen.
- Der zuletzt bekannte Stand der ACE-Box wird gespeichert und nach einem Neustart der Bridge als '(letzter Stand)' angezeigt, bis der Drucker neu meldet.
- Laufende Drucke erscheinen in der Druckhistorie mit dem Status 'Laeuft' (nicht mehr als 'Fehlgeschlagen').

Gedruckte Produkte (Druckhistorie, eigener Menuepunkt):

- Importiert die Druckhistorie aus der Anycubic-Cloud (Name, Dauer, Drucker, Gewicht, Status). Die Cloud liefert keine Spulenzuordnung, deshalb wird nichts automatisch abgezogen.
- 'Zuordnen' bucht den Verbrauch auf eine Spule (Gramm aenderbar), 'Ohne Abzug' markiert einen Druck als erledigt, 'Neuer Druck' legt manuelle Eintraege an. Filter nach Drucker, Status und Name.

Statistik (eigener Menuepunkt): Verbrauch, Drucke und Prognose; Farbnamen koennen an der Spule gepflegt werden und erscheinen in der Auswertung.

## Aufbau

```
docker-compose.yml
dashboard/   Frontend (nginx, statische SPA) + Reverse-Proxy zu Spoolman/Storage/Anycubic-Bridge
storage/     Eigenes Lagerplatz- und Label-Backend (FastAPI + SQLite + Playwright/Chromium fuer Label-Export)
bridge/      Anycubic-Cloud-Bridge (FastAPI): liest Live-Druckstatus/ACE-Slots per Anycubic-Account aus und bucht Verbrauch in Spoolman
```

Alle vier Dienste (Spoolman, Storage, Dashboard, Anycubic-Bridge) sind Teil desselben Compose-Projekts und starten gemeinsam mit `docker compose up -d`. Die Anycubic-Integration ist komplett optional **zur Nutzung** - ohne Anycubic-Account einfach ignorieren, unter Einstellungen -> Anycubic-Integration im Dashboard konfigurieren, wer sie braucht.

Spoolman selbst laeuft als offizielles Image (`ghcr.io/donkie/spoolman`), Konfiguration/Doku dort: https://github.com/Donkie/Spoolman

## Daten

Beide Datenbanken (Spoolman, Lagerplaetze/Label-Vorlagen) starten leer und liegen in benannten Docker-Volumes (`spoolman_data`, `storage_data`). Zum Zuruecksetzen: `docker compose down -v`.

## Bekannte Einschraenkungen (Stand dieser Version)

- Kamera-Scan ist nur in einem sicheren Kontext (HTTPS oder `localhost`) verfuegbar - siehe Hinweis oben.

## Aenderungsverlauf

Die aktuelle Version steht im Footer des Dashboards (dort auch der Aenderungsverlauf).

- **v1.8.1 (2026-10-29)**: Druckeransicht: aktive externe Spule der Kobra X wird in Karte und Schaubild markiert, Fuellstandsring zeigt den Spoolman-Wert statt des unzuverlaessigen Druckerwerts.
- **v1.8.0 (2026-10-25)**: Wartungsbuch: Werte und Anleitungs-Links aus dem Anycubic-Wiki, Ersatzteile mit Druckerzuordnung/Sortierung/Filter, Einbauen und Ausbauen von Teilen (Lebensdauer erreicht, defekt, zurueck ins Lager) mit optionalem Einkaufslisten-Eintrag, Duesen 0,2/0,4/0,6/0,8 als Standard-Artikel.
- **v1.7.0 (2026-10-24)**: Neu: Wartungsbuch - Wartungsplan je Drucker nach Druckstunden, Zustands-Score, Prognose, Duese und Druckplatte mit eigener Laufzeit (abrasive Materialien zaehlen dreifach), Ersatzteillager, Kosten, Grosser Service, Service-Heft als PDF.
- **v1.6.1 (2026-10-24)**: Externe Spulen neben dem Drucker, Lagerpltze mit mitlaufender Druckerspalte neben den Dryboxen, volle Fensterbreite (responsiv).
- **v1.6.0 (2026-10-24)**: Neue Druckeransicht: ACE oben mit Schlauch, Rollen in echten Farben, aktiver Slot leuchtet, großer Fortschritt mit Schicht x/y und Infozeilen.
- **v1.5.1 (2026-10-24)**: ACE/AMS zuverlässig im Druckerrahmen, Knopf "ACE/AMS hinzufügen", Warnung bei ACE ohne Drucker.
- **v1.5.0 (2026-10-24)**: Slot-Karten mit Spulenring, Zuordnen auf zwei Spulen, Slot-Erkennung per Farbe (Kobra X).
- **v1.4.0 (2026-10-16)**: Seitenleisten-Navigation; Drucker-Seite mit Live-Daten aus der Anycubic-Bridge (ACE-Boxen, Restmenge in Gramm, Abweichungshinweis, Buchen/Angleichen am Slot); Druckhistorie 'Gedruckte Produkte'; Statistik; Farbnamen; Drybox/Drucker-Assistent; laufende Drucke nicht mehr als fehlgeschlagen; Bridge synchronisiert die Druckhistorie automatisch alle 30 Minuten (PRINT_SYNC_MIN), anycubic-cloud-api 0.4.36.
- **v1.3.0 (2026-09-28)**: Versionsanzeige und Aenderungsverlauf im Footer.
- **v1.2.0 (2026-09-28)**: Ebenen und Plaetze eines bestehenden Geraets nachtraeglich aenderbar.
- **v1.1.0 (2026-09-28)**: Restliche Feldnamen im Etikettendesigner uebersetzt; mehrere Dryboxen getestet.
- **v1.0.0 (2026-09-27)**: Umbenennung zu 'The Filament Storage System', vollstaendige DE/EN-Uebersetzung.

## Update auf eine neuere Version

Wer dieses Repo bereits laufen hat und auf den neuesten Stand aktualisieren moechte:

```bash
git pull
docker compose down
docker compose up -d --build
```

Die SQLite-Datenbank im `storage`-Dienst migriert ihr Schema beim Start automatisch (fehlende Spalten/Tabellen werden per `ALTER TABLE` ergaenzt) - ein manueller DB-Migrationsschritt ist fuer bestehende Installationen nicht noetig. Eure Daten in den Volumes `spoolman_data` und `storage_data` bleiben beim Update erhalten (nur `docker compose down -v` wuerde sie loeschen - das NICHT verwenden, wenn ihr eure Daten behalten wollt).

## Status

In aktiver Entwicklung. Rueckmeldungen, Bug-Reports und Feature-Wuensche sind herzlich willkommen - am liebsten als Issue in diesem Repo.
