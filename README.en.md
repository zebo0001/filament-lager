# The Filament Storage System

*[Deutsch](README.md) | English*

Self-hosted storage management system for 3D printing filament: [Spoolman](https://github.com/Donkie/Spoolman) for spool tracking, plus a custom storage-location module that assigns spools to physical locations (printer, AMS/ACE unit, dry box, ...) - including drag & drop, a shopping list for empty rolls, a visual storage overview, a built-in label designer (with QR/barcode export as PNG/PDF), and a scan-driven workflow for receiving new spools and assigning storage locations (hardware scanner or phone camera).

Running in production for us for several weeks now. Feedback, bug reports and feature suggestions are very welcome - preferably as an issue in this repo.

## Screenshot

![Storage locations view](docs/dashboard-screenshot.png)

## Requirements

- Docker Desktop (Windows/Mac) or Docker + Compose plugin (Linux)
- The `storage` service is built on a Playwright/Chromium base image (needed for PNG/PDF label export) - the image is correspondingly larger, so the first `docker compose up -d` takes a bit longer to build than with a slim Python image.

## Getting started

```bash
docker compose up -d
```

Then:

- Dashboard: http://localhost:8093
- Spoolman (full interface): http://localhost:8091

Ports can be adjusted via a `.env` file (template: `.env.example`).

**Important for camera scanning:** Camera-based QR scanning (in scan mode, as an alternative to a hardware scanner) requires a secure browser context (HTTPS or `localhost`). Over `http://localhost:8093` on the same machine this works out of the box. If you access the dashboard from a phone via the Docker host's LAN IP (e.g. `http://192.168.x.x:8093`), the camera option is automatically disabled (with an explanatory note) - in that case the only input path left is an external hardware barcode/QR scanner (HID keyboard emulation), or you can put the dashboard behind your own reverse proxy with HTTPS.

## What to test

Core features:

- Add spools in Spoolman (material, manufacturer, color, including multi-color), including an article-number field
- Configure storage locations (Dashboard -> Storage locations): printer, AMS/ACE unit, dry box
- Assign spools to locations via drag & drop or the assignment dialog ("On printer/AMS", "In dry box")
- Click a spool name in the table -> a detail/edit modal opens (price, weights, lot number, comment, temperature overrides, filament-type fields) - editing after the fact is supported
- Try "Spool empty" (archives the spool in Spoolman, frees the slot, adds an entry to the shopping list including the article number)
- Search and pagination in the spool directory
- Reorder dashboard panels via the settings button

Label designer (its own menu item in the dashboard):

- Build custom label templates via drag & drop (text with Spoolman variables like name/material/manufacturer/color, spool icon, color swatch, barcode/QR code)
- Templates are typed as either spool or filament (switch in the editor) - the QR code content automatically follows the selected type
- Live QR preview directly in the design tab (no more placeholder - a real QR code while you edit)
- Design and print tabs are separate: the print tab lets you select multiple spools/filaments for a label sheet (sheet-tile printing), including a live preview of the sheet
- The QR code automatically embeds the app logo in its center
- QR content follows the schema `WEB+SPOOLMAN:S-<spool_id>` or `WEB+SPOOLMAN:F-<filament_id>` (compatible with the scan format used by Spoolman's own label designer; scanning is case-insensitive)
- Export templates as PNG or PDF (runs via headless Chromium in the `storage` service) and print them with a label printer or laser printer

Scan-driven workflow (hardware barcode/QR scanner with HID keyboard emulation, no driver needed - or alternatively the phone camera, see the HTTPS note above):

- The spool ID is shown directly in the spool table
- Slot label generation and a print view for storage locations
- Scan overlay with status display while scanning; camera scanning can be enabled via a toggle (the setting is stored per device in the browser)
- Fully scan-only receiving workflow: scanning a filament QR code automatically creates a new spool, and scanning a location code right after assigns it directly - no manual dialog interaction needed
- Alternatively, in the "New spool" dialog you can scan a printed filament QR label to auto-fill material/manufacturer/color

Printers page (dedicated dashboard section, since v1.4.0):

- Shows all Anycubic printers connected via the bridge live (status, current print job, ACE slot occupancy) together with manually added placeholder printers in one unified view
- Active prints show a Spooly-style progress card: filename, large percentage, remaining time, estimated completion time, progress bar
- Idle printers (status "available"/"online"/"standby") show a calm, non-animated illustration instead of the printing animation

## Structure

```
docker-compose.yml
dashboard/ Frontend (nginx, static SPA) + reverse proxy to Spoolman/Storage
storage/ Custom storage-location and label backend (FastAPI + SQLite + Playwright/Chromium for label export)
```

Spoolman itself runs as the official image (`ghcr.io/donkie/spoolman`); configuration/docs there: https://github.com/Donkie/Spoolman

## Data

Both databases (Spoolman, storage locations/label templates) start out empty and live in named Docker volumes (`spoolman_data`, `storage_data`). To reset: `docker compose down -v`.

## Known limitations (as of this version)

- Camera scanning is only available in a secure context (HTTPS or `localhost`) - see the note above.

## Status

Under active development. Feedback, bug reports and feature requests are very welcome - preferably as an issue in this repo.
