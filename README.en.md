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
- Create devices via the Device Wizard (Dashboard -> Storage locations -> Device Wizard): printer (optionally with AMS/ACE feed unit) or dry box, with a live preview while you fill in the fields. All device types go through the same wizard now, no separate form needed
- Nested devices: a printer with AMS/ACE can contain several feed boxes as independent child devices. The storage overview shows this nesting indented
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
- Storage locations can be linked to one specific ACE box on a printer (not just the printer as a whole) - important when a printer has several feed boxes

New in v1.5.0 (printer page and history):

- Every slot card shows a spool ring in the filament colour; the fill is the remaining amount reported by the printer, with the percentage in the middle. The slot currently feeding is outlined.
- History: 'Assign' can split a print across two spools (e.g. after a spool change mid-print); on a spool change during a running print the dashboard asks.
- Anycubic bridge: if a printer (Kobra X) reports no active slot, the slot is determined by colour and material. With several identical-looking spools it deliberately does not book automatically.

Printer page, live data and reconciliation (v1.4.0):

- ACE boxes are shown with colour, material and SKU; the slot currently fed is marked. The ACE port on the device is labelled 'ACE'.
- Remaining amount per slot is shown in grams ('Printer approx. 350 g - Spoolman 690 g'). The printer value is an estimate (remaining percent times the starting weight of the assigned spool). A warning appears from 15 percent deviation.
- Usage can be booked directly on the slot: enter grams and press 'Book' or 'Adjust' (books the difference down to the printer value, only offered when Spoolman shows more). Both ask for confirmation first. Better not to adjust while a print is running.
- The last known ACE box state is stored and shown as '(last state)' after a bridge restart until the printer reports again.
- Running prints show up in the print history with the status 'Running' (no longer 'Failed').

Printed products (print history, own menu entry):

- Imports the print history from the Anycubic cloud (name, duration, printer, weight, status). The cloud does not report which spool was used, so nothing is deducted automatically.
- 'Assign' books the usage onto a spool (grams editable), 'No deduction' marks a print as handled, 'New print' adds manual entries. Filters by printer, status and name.

Statistics (own menu entry): usage, prints and forecast; colour names can be maintained on the spool and appear in the reports.

## Structure

```
docker-compose.yml
dashboard/ Frontend (nginx, static SPA) + reverse proxy to Spoolman/Storage/Anycubic bridge
storage/ Custom storage-location and label backend (FastAPI + SQLite + Playwright/Chromium for label export)
bridge/ Anycubic cloud bridge (FastAPI): reads live print status/ACE slots via an Anycubic account and books consumption in Spoolman
```

All four services (Spoolman, Storage, Dashboard, Anycubic bridge) are part of the same Compose project and start together with `docker compose up -d`. The Anycubic integration is entirely optional **to use** - ignore it if you have no Anycubic account, or configure it under Settings -> Anycubic Integration in the dashboard if you do.

Spoolman itself runs as the official image (`ghcr.io/donkie/spoolman`); configuration/docs there: https://github.com/Donkie/Spoolman

## Data

Both databases (Spoolman, storage locations/label templates) start out empty and live in named Docker volumes (`spoolman_data`, `storage_data`). To reset: `docker compose down -v`.

## Known limitations (as of this version)

- Camera scanning is only available in a secure context (HTTPS or `localhost`) - see the note above.

## Changelog

The current version is shown in the dashboard footer (including the changelog).

- **v1.9.0 (2026-10-29)**: New: spool calculator (menu item). Weight and empty spool weight (manufacturer list, Spoolman values or custom entries) give the fill level; assign to a spool or create a new one. Spool number in tooltips.
- **v1.8.1 (2026-10-29)**: Printer view: the active external spool (Kobra X) is highlighted in card and diagram; level ring shows the Spoolman value instead of the unreliable printer value.
- **v1.8.0 (2026-10-25)**: Maintenance log: values and guide links from the Anycubic wiki, spare parts with printer assignment/sorting/filter, install and remove parts (worn out, defective, back to stock) with optional shopping-list entry, nozzles 0.2/0.4/0.6/0.8 as standard items.
- **v1.7.0 (2026-10-24)**: New: maintenance log - per-printer plan based on print hours, condition score, forecast, nozzle and build plate with own runtime (abrasive materials count triple), spare parts, costs, major service, PDF service booklet.
- **v1.6.1 (2026-10-24)**: External spools beside the printer, storage view with sticky printer column next to the dryboxes, full-width responsive layout.
- **v1.6.0 (2026-10-24)**: New printer view: ACE on top with hose, spools in real colours, glowing active slot, big progress with layer x/y and info rows.
- **v1.5.1 (2026-10-24)**: ACE/AMS reliably shown inside the printer frame, "add ACE/AMS" button, warning for an ACE without a printer.
- **v1.5.0 (2026-10-24)**: Slot cards with spool ring, assign a print to two spools, slot detection by colour (Kobra X).
- **v1.4.0 (2026-10-16)**: sidebar navigation; printer page with live data from the Anycubic bridge (ACE boxes, remaining amount in grams, deviation hint, book/adjust on the slot); print history 'Printed products'; statistics; colour names; dry box/printer wizard; running prints no longer shown as failed; the bridge syncs the print history automatically every 30 minutes (PRINT_SYNC_MIN), anycubic-cloud-api 0.4.36.
- **v1.3.0 (2026-09-28)**: version indicator and changelog in the footer.
- **v1.2.0 (2026-09-28)**: levels and slots of an existing device can be changed afterwards.
- **v1.1.0 (2026-09-28)**: remaining label designer field names translated; multiple dry boxes tested.
- **v1.0.0 (2026-09-27)**: renamed to 'The Filament Storage System', full DE/EN translation.

## Updating to a newer version

If you already have this repo running and want to update to the latest state:

```bash
git pull
docker compose down
docker compose up -d --build
```

The SQLite database in the `storage` service migrates its schema automatically on startup (missing columns/tables are added via `ALTER TABLE`) - no manual DB migration step is needed for existing installations. Your data in the `spoolman_data` and `storage_data` volumes is preserved across the update (only `docker compose down -v` would delete it - do NOT use that if you want to keep your data).

## Status

Under active development. Feedback, bug reports and feature requests are very welcome - preferably as an issue in this repo.
