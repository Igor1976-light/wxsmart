# WXsmart Live-Dashboard – Umsetzungsplan

## Zielbild
Browser-basiertes Live-Dashboard für WXsmart mit:
- Tool1/Tool2-Status
- Tip-Informationen
- Temperatur in °C (live)
- Leistung/Power
- Betriebsdauer / Counter / OperatingHours
- Seriennummern (Tool/Tip)
- Online/Offline-Status
- Historie (Kurven)

---

## Phase 0 – Scope, Datenmodell, Architektur (MVP-Definition)

### 0.1 Funktionsumfang MVP festlegen
- [ ] Muss-Felder definieren (Temperatur, Power, Counter/Time, SerialNumber, ONLINE)
- [ ] Soll-Felder definieren (Firmware, DeviceName, IP, OperatingHours)
- [ ] Update-Ziel festlegen (eventbasiert pro MQTT-Message)
- [ ] UI-Ansicht festlegen (Tool-Kacheln + Station-Panel + kleine Trends)

### 0.2 Topic-Mapping dokumentieren
- [ ] MQTT-Topics in semantische Felder mappen
- [ ] Einheitentransformationen festlegen (z. B. Temperatur = raw/10)
- [ ] Feldnamen normieren (snake_case im Backend, lesbar im Frontend)
- [ ] Umgang mit fehlenden/alten Werten definieren (TTL/"stale")

### 0.3 Architekturentscheidung
- [ ] Backend: Python + FastAPI
- [ ] Transport: WebSocket (Fallback SSE optional)
- [ ] Frontend: HTML/JS + Chart.js
- [ ] Optional Persistenz: SQLite für Historie

---

## Phase 1 – Backend-Grundlage (Daten-Aggregator)

### 1.1 Projektstruktur anlegen
- [ ] `app/main.py` (FastAPI Startpunkt)
- [ ] `app/mqtt_ingest.py` (MQTT Subscriber + Parser)
- [ ] `app/state_store.py` (In-Memory Zustand)
- [ ] `app/models.py` (Pydantic DTOs)
- [ ] `app/config.py` (Env-Konfiguration)

### 1.2 MQTT-Ingest implementieren
- [ ] Verbindungsaufbau zu MQTT Broker (Host/Port/Topic per ENV)
- [ ] Robuster Reconnect + Backoff
- [ ] Topic-Parser für Tool1/Tool2/Tip/Station
- [ ] Retain/Non-Retain korrekt verarbeiten

### 1.3 Datenmodell (serverseitig)
- [ ] `station_state` (online, firmware, device_name, last_seen)
- [ ] `tools[tool_id]` (temperature_c, power_w, counter_time, serial)
- [ ] `tips[tip_id]` (id, serial, assignment)
- [ ] Zeitstempel pro Feld (`updated_at`)

### 1.4 Live-Streaming API
- [ ] WebSocket Endpoint `/ws/live`
- [ ] Snapshot beim Connect senden
- [ ] Delta-Events bei Änderungen senden
- [ ] Heartbeat/Ping implementieren

### 1.5 REST-API (Basis)
- [ ] `GET /api/state` (aktueller Gesamtzustand)
- [ ] `GET /api/tools` (nur Tooldaten)
- [ ] `GET /api/station` (Station-Metadaten)
- [ ] OpenAPI Beschreibung prüfen

---

## Phase 2 – Frontend-Dashboard (Browser, live)

### 2.1 Grundlayout
- [ ] Header mit Verbindungsstatus
- [ ] Kachel `Tool1`
- [ ] Kachel `Tool2`
- [ ] Bereich `Tips`
- [ ] Bereich `Station`

### 2.2 Live-Bindings
- [ ] WebSocket-Client implementieren
- [ ] Snapshot rendern
- [ ] Delta-Updates einpflegen
- [ ] Reconnect-Logik im Browser

### 2.3 Visualisierung
- [ ] Temperatur groß + farbcodiert
- [ ] Power als aktuelle Kennzahl
- [ ] Counter/OperatingHours lesbar formatieren
- [ ] Seriennummern kompakt anzeigen

### 2.4 Trends/Charts
- [ ] Ringpuffer je Tool (z. B. letzte 300 Punkte)
- [ ] Temperatur-Linienchart pro Tool
- [ ] Optional: Power-Linie
- [ ] Zeitachse performant halten

### 2.5 UX/Usability
- [ ] Stale-Werte optisch kennzeichnen
- [ ] Offline-Banner bei MQTT-Verlust
- [ ] Letztes Update pro Feld anzeigen
- [ ] Mobile/Tablet responsive machen

---

## Phase 3 – Alarmierung & Datenqualität

### 3.1 Regeln
- [ ] Alarmregel `keine Temperatur seit X Sekunden`
- [ ] Alarmregel `Tool offline`
- [ ] Alarmregel `Temperatur > Schwellwert`

### 3.2 UI-Alarme
- [ ] Alarmleiste oben
- [ ] Alarmhistorie (letzte N Ereignisse)
- [ ] Quittierung im UI (optional)

### 3.3 Datenvalidierung
- [ ] Plausibilitätschecks (negative Temp, Sprünge)
- [ ] Unit-Umrechnung zentralisieren
- [ ] Fehlende Felder robust behandeln

---

## Phase 4 – Persistenz (optional, aber empfohlen)

### 4.1 SQLite-Ingestion
- [ ] Tabelle `telemetry` (timestamp, topic, tool, value_raw, value_norm)
- [ ] Tabelle `events` (alarms, reconnects)
- [ ] Schreibrate begrenzen (sampling/throttling)

### 4.2 Historien-API
- [ ] `GET /api/history?tool=Tool1&metric=temperature&from=...&to=...`
- [ ] Aggregation (1s/5s/30s Buckets)
- [ ] Frontend-Chart auf API umstellen

---

## Phase 5 – Qualität, Tests, Betrieb

### 5.1 Tests
- [ ] Parser-Tests für Topic→Feld-Mapping
- [ ] API-Tests für REST/WS
- [ ] Reconnect/Offline-Tests
- [ ] Snapshot-vs-Delta Konsistenztests

### 5.2 Betrieb/Deployment
- [ ] `.env.example` pflegen
- [ ] Startskript (`run_dashboard.sh`)
- [ ] Logging-Strategie (rotating logs)
- [ ] Optional Dockerfile

### 5.3 Dokumentation
- [ ] README: Setup/Start/ENV
- [ ] Topic-Mapping Tabelle
- [ ] Troubleshooting (keine Temperatur, Broker down)

---

## Vorschlag für Umsetzung in Iterationen

### Iteration A (1–2 Tage, MVP)
- [ ] Backend MQTT + `/api/state`
- [ ] WebSocket live
- [ ] Frontend mit Tool1/Tool2 Kacheln
- [ ] Temperatur/Power/Counter/Serial live sichtbar

### Iteration B (1 Tag)
- [ ] Charts + Stale-Handling + Reconnect UX
- [ ] Temp-alarm `keine Daten seit Xs`

### Iteration C (1–2 Tage)
- [ ] SQLite Historie + History API
- [ ] Alarmhistorie + Export

---

## Risiken & Gegenmaßnahmen
- [ ] Unregelmäßige Temperaturtopics → Stale-Indikator + Heartbeat
- [ ] Topic-Änderungen Firmware-seitig → Mapping zentral kapseln
- [ ] WebSocket Verbindungsabbrüche → Auto-Reconnect + Backoff
- [ ] Zu hohe Eventrate → Delta-Only + throttling

---

## Definition of Done
- [ ] Browser zeigt Tool1/Tool2 Temperaturen live in °C
- [ ] Tool- und Tip-Seriennummern sind sichtbar
- [ ] Betriebsdauer/Counter werden fortlaufend aktualisiert
- [ ] Online/Offline-Zustand ist eindeutig erkennbar
- [ ] Reconnect funktioniert ohne manuellen Reload
- [ ] Basisdoku für Start und Betrieb vorhanden
