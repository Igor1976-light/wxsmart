# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false
from datetime import datetime
import csv
import json
import os
import signal
import sys
import time
from typing import Any

import paho.mqtt.client as mqtt

signal.signal(signal.SIGPIPE, signal.SIG_DFL)


BROKER_HOST = os.getenv("MQTT_HOST", "localhost")
BROKER_PORT = 9001
DEFAULT_SERIAL = os.getenv("WXSMART_SERIAL", "").strip()
TOPIC_FILTER = os.getenv("MQTT_TOPIC") or (
    f"WXSMART/{DEFAULT_SERIAL}/#" if DEFAULT_SERIAL else "WXSMART/#"
)
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOG_FILE = os.path.join(PROJECT_DIR, "temp", "wxsmart_messages.log")
LOG_FILE = os.getenv("MQTT_LOG_FILE", DEFAULT_LOG_FILE)
VERBOSE = os.getenv("MQTT_VERBOSE", "1").lower() in ("1", "true", "yes")
COMPACT_VIEW = os.getenv("MQTT_COMPACT", "1").lower() in ("1", "true", "yes")
MODE = os.getenv("MQTT_MODE", "monitor").lower()
DISCOVERY_SECONDS = int(os.getenv("MQTT_DISCOVERY_SECONDS", "10"))
DEFAULT_DISCOVERY_CSV = os.path.join(PROJECT_DIR, "temp", "wxsmart_status_topics.csv")
DISCOVERY_CSV = os.getenv("MQTT_DISCOVERY_CSV", DEFAULT_DISCOVERY_CSV)
DEFAULT_LIVE_CSV = os.path.join(PROJECT_DIR, "temp", "wxsmart_live_metrics.csv")
LIVE_CSV = os.getenv("MQTT_LIVE_CSV", DEFAULT_LIVE_CSV)
DEFAULT_TEMP_LOG_FILE = os.path.join(PROJECT_DIR, "temp", "wxsmart_temperature.log")
TEMP_LOG_FILE = os.getenv("MQTT_TEMP_LOG_FILE", DEFAULT_TEMP_LOG_FILE)
LIVE_IDLE_WARN_SECONDS = int(os.getenv("MQTT_LIVE_IDLE_WARN_SECONDS", "12"))

message_count = 0
error_count = 0
start_time = datetime.now()
status_topic_values: dict[str, str] = {}
status_topic_counts: dict[str, int] = {}
all_topic_values: dict[str, str] = {}
all_topic_counts: dict[str, int] = {}
live_csv_header_written = False
live_message_count = 0
last_live_topic_at: datetime | None = None
temp_message_count = 0
last_temp_topic_at: datetime | None = None


def is_temperature_read_topic(topic: str) -> bool:
    return (
        "/STATUS/Tool1/Temperature/Read" in topic
        or "/STATUS/Tool2/Temperature/Read" in topic
    )


def is_live_topic(topic: str) -> bool:
    if not topic.startswith("WXSMART/"):
        return False
    live_markers = (
        "/STATUS/ONLINE",
        "/Temperature",      # trifft /Temperature, /Temperature/Read, /Temperature/Set
        "/Power",            # trifft /Power, /Power/Read, /Power/Set
        "/Counter/Time",
        "/State",
    )
    return any(marker in topic for marker in live_markers)


def format_live_display(topic: str, payload_value: str) -> str:
    if "Temperature" in topic and payload_value.isdigit():
        return f"{int(payload_value)/10.0:.1f}°C"
    if "Power" in topic and payload_value.isdigit():
        if "/Read" in topic:
            return f"{int(payload_value)/10.0:.1f}W"
        return f"{payload_value}W"
    return payload_value


def write_live_csv_row(
    timestamp: str,
    topic: str,
    payload_value: str,
    qos: int,
    retain: bool,
    counter: int,
) -> None:
    global live_csv_header_written
    if not LIVE_CSV:
        return

    try:
        live_dir = os.path.dirname(LIVE_CSV)
        if live_dir:
            os.makedirs(live_dir, exist_ok=True)

        header_needed = not live_csv_header_written and (
            not os.path.exists(LIVE_CSV) or os.path.getsize(LIVE_CSV) == 0
        )
        with open(LIVE_CSV, "a", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            if header_needed:
                writer.writerow(["timestamp", "topic", "value", "display", "qos", "retain", "msg_no"])
                live_csv_header_written = True
            writer.writerow([
                timestamp,
                topic,
                payload_value,
                format_live_display(topic, payload_value),
                qos,
                int(retain),
                counter,
            ])
    except OSError as error:
        print(f"[LIVE_CSV_ERROR] CSV schreiben fehlgeschlagen: {error}", file=sys.stderr)


def write_temperature_log_row(log_line: str) -> None:
    if not TEMP_LOG_FILE:
        return
    try:
        temp_log_dir = os.path.dirname(TEMP_LOG_FILE)
        if temp_log_dir:
            os.makedirs(temp_log_dir, exist_ok=True)
        with open(TEMP_LOG_FILE, "a", encoding="utf-8") as file_handle:
            file_handle.write(log_line + "\n")
    except OSError as error:
        print(f"[TEMP_LOG_ERROR] Datei schreiben fehlgeschlagen: {error}", file=sys.stderr)


def log_message(msg: str) -> None:
    """Gibt Nachricht auf Stdout und optional in Datei aus."""
    try:
        print(msg, flush=True)
    except BrokenPipeError:
        return
    if LOG_FILE:
        try:
            log_dir = os.path.dirname(LOG_FILE)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception as err:
            print(f"[LOG_ERROR] Datei schreiben fehlgeschlagen: {err}", file=sys.stderr)


def on_connect(
    client: Any,
    userdata: Any,
    flags: Any,
    reason_code: Any,
    properties: Any = None,
) -> None:
    if reason_code == 0:
        uptime = (datetime.now() - start_time).total_seconds()
        log_message(f"✔ Verbunden mit Broker auf {BROKER_HOST}:{BROKER_PORT} (nach {uptime:.1f}s)")
        result, mid = client.subscribe(TOPIC_FILTER, qos=0)
        log_message(f"✔ Subscribe auf '{TOPIC_FILTER}' gesendet (result={result}, mid={mid})")
    else:
        log_message(f"✖ Verbindungsfehler: {reason_code}")


def parse_payload_value(payload_text: str) -> str:
    stripped = payload_text.strip()
    if not stripped:
        return "<leer>"
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return payload_text

    if isinstance(parsed, (dict, list)):
        return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
    return str(parsed)


def format_compact_line(topic: str, payload_value: str, timestamp: str, counter: int) -> str:
    parts = topic.split("/")
    if len(parts) >= 4 and parts[0].upper() == "WXSMART":
        device_id = parts[1]
        path = "/".join(parts[3:])
        path_short = path.replace("/", ".")
        display_value = payload_value

        if "Temperature" in path and payload_value.isdigit():
            celsius = int(payload_value) / 10.0
            display_value = f"{celsius:.1f} °C (raw={payload_value})"

        return f"[{timestamp}] #{counter} {device_id} | {path_short} = {display_value}"
    return f"[{timestamp}] #{counter} {topic} = {payload_value}"


def is_probably_json(payload_text: str) -> bool:
    stripped = payload_text.strip()
    return stripped.startswith("{") or stripped.startswith("[")


def on_message(client: Any, userdata: Any, msg: Any) -> None:
    global message_count, error_count, live_message_count, last_live_topic_at, temp_message_count, last_temp_topic_at
    message_count += 1

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    elapsed = (datetime.now() - start_time).total_seconds()
    payload_bytes = bytes(msg.payload)
    payload_text = payload_bytes.decode("utf-8", errors="replace")
    payload_value = parse_payload_value(payload_text)

    if msg.topic.startswith("WXSMART/"):
        all_topic_values[msg.topic] = payload_value
        all_topic_counts[msg.topic] = all_topic_counts.get(msg.topic, 0) + 1
    if "/STATUS/" in msg.topic and msg.topic.startswith("WXSMART/"):
        status_topic_values[msg.topic] = payload_value
        status_topic_counts[msg.topic] = status_topic_counts.get(msg.topic, 0) + 1

    is_temp_read = is_temperature_read_topic(msg.topic)

    if MODE == "discover":
        return

    if MODE == "temp":
        if is_temp_read:
            temp_message_count += 1
            last_temp_topic_at = datetime.now()
            line = format_compact_line(msg.topic, payload_value, timestamp, message_count)
            log_message(line)
            write_temperature_log_row(line)
            if VERBOSE:
                log_message(f"  qos={msg.qos} retain={msg.retain} bytes={len(payload_bytes)}")
        return

    if MODE == "live":
        if is_live_topic(msg.topic):
            live_message_count += 1
            last_live_topic_at = datetime.now()
            line = format_compact_line(msg.topic, payload_value, timestamp, message_count)
            log_message(line)
            if is_temp_read:
                temp_message_count += 1
                last_temp_topic_at = datetime.now()
                write_temperature_log_row(line)
            write_live_csv_row(
                timestamp=timestamp,
                topic=msg.topic,
                payload_value=payload_value,
                qos=msg.qos,
                retain=msg.retain,
                counter=message_count,
            )
            if VERBOSE:
                log_message(f"  qos={msg.qos} retain={msg.retain} bytes={len(payload_bytes)}")
        return

    if COMPACT_VIEW:
        line = format_compact_line(msg.topic, payload_value, timestamp, message_count)
        log_message(line)
        if is_temp_read:
            temp_message_count += 1
            last_temp_topic_at = datetime.now()
            write_temperature_log_row(line)
        if VERBOSE:
            log_message(f"  qos={msg.qos} retain={msg.retain} bytes={len(payload_bytes)}")
        return

    log_message(f"\n{'='*80}")
    log_message(f"[{timestamp}] Nachricht #{message_count} (Laufzeit: {elapsed:.1f}s)")
    log_message(f"Topic   : {msg.topic}")
    log_message(f"QoS     : {msg.qos}")
    log_message(f"Retain  : {msg.retain}")
    log_message(f"Bytes   : {len(payload_bytes)}")
    log_message(f"Text    : {payload_text}")

    try:
        parsed = json.loads(payload_text)
        log_message(f"JSON    : {json.dumps(parsed, ensure_ascii=False, indent=2)}")
    except json.JSONDecodeError as err:
        if is_probably_json(payload_text):
            error_count += 1
            log_message(f"JSON    : <FEHLER: {err}>")
        else:
            log_message("JSON    : <kein JSON-Format>")

    if VERBOSE:
        log_message(f"Hex     : {payload_bytes.hex(' ')}")


def on_disconnect(
    client: Any,
    userdata: Any,
    disconnect_flags: Any,
    reason_code: Any,
    properties: Any = None,
) -> None:
    elapsed = (datetime.now() - start_time).total_seconds()
    log_message(f"⚠ Verbindung getrennt: {reason_code} (nach {elapsed:.1f}s, {message_count} Nachrichten)")


def on_subscribe(
    client: Any,
    userdata: Any,
    mid: int,
    reason_codes: Any,
    properties: Any = None,
) -> None:
    log_message(f"✔ Subscription bestätigt (mid={mid}, reason_codes={reason_codes})")


def on_log(client: Any, userdata: Any, level: int, buf: str) -> None:
    if VERBOSE:
        log_message(f"[LOG] {buf}")


def create_client() -> Any:
    callback_api_version = getattr(getattr(mqtt, "CallbackAPIVersion", None), "VERSION2", None)
    if callback_api_version is not None:
        mqtt_client = mqtt.Client(
            callback_api_version=callback_api_version,
            transport="websockets",
        )
    else:
        mqtt_client = mqtt.Client(transport="websockets")
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_subscribe = on_subscribe
    mqtt_client.on_log = on_log
    return mqtt_client


def connect_with_fallback(client: Any, keepalive: int = 60) -> str:
    hosts = [BROKER_HOST, "localhost", "127.0.0.1"]
    tried_hosts = []

    for host in hosts:
        if host in tried_hosts:
            continue
        tried_hosts.append(host)

        try:
            log_message(f"Verbinde zu {host}:{BROKER_PORT} (WebSocket) …")
            client.connect(host, BROKER_PORT, keepalive=keepalive)
            return host
        except ConnectionRefusedError:
            log_message(f"✖ Verbindung abgelehnt auf {host}:{BROKER_PORT}")
        except OSError as error:
            log_message(f"✖ Netzwerkfehler auf {host}:{BROKER_PORT} -> {error}")

    raise ConnectionError(
        f"Keine Verbindung möglich. Geprüfte Hosts: {', '.join(tried_hosts)} auf Port {BROKER_PORT}."
    )


def main() -> int:
    client = create_client()
    try:
        active_host = connect_with_fallback(client)
    except ConnectionError as error:
        log_message(str(error))
        log_message("Hinweis: Dein Broker ist lokal erreichbar auf localhost:9001.")
        log_message("Setze bei Bedarf: export MQTT_HOST=localhost")
        return 1

    log_message("")
    log_message(f"{'='*80}")
    log_message(f"WXSMART MQTT-Monitor gestartet")
    log_message(f"{'='*80}")
    log_message(f"Broker     : {active_host}:{BROKER_PORT} (WebSocket)")
    log_message(f"Topic-Filter: {TOPIC_FILTER}")
    log_message(f"Log-Datei  : {LOG_FILE if LOG_FILE else '(Datei-Logging deaktiviert)'}")
    log_message(f"Temp-Log   : {TEMP_LOG_FILE if TEMP_LOG_FILE else '(deaktiviert)'}")
    log_message(f"Verbose    : {VERBOSE}")
    log_message(f"Kompakt    : {COMPACT_VIEW}")
    log_message(f"Modus      : {MODE}")
    log_message(f"Start-Zeit : {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    log_message(f"{'='*80}")
    log_message("")

    if MODE == "discover":
        log_message(f"Discovery läuft für {DISCOVERY_SECONDS}s …")
        client.loop_start()
        try:
            time.sleep(DISCOVERY_SECONDS)
        finally:
            client.loop_stop()
            client.disconnect()

        log_message("")
        log_message(f"{'='*80}")
        log_message("Gefundene Topics (alle Kategorien)")
        log_message(f"{'='*80}")

        if not all_topic_values:
            log_message("Keine Topics empfangen.")
            log_message("Tipp: Erhöhe MQTT_DISCOVERY_SECONDS oder prüfe den Topic-Filter.")
            return 0

        # Ausgabe gruppiert nach Kategorie (3. Segment des Topics)
        last_category = ""
        for index, topic in enumerate(sorted(all_topic_values.keys()), start=1):
            parts = topic.split("/")
            category = parts[2] if len(parts) > 2 else ""
            if category != last_category:
                log_message(f"")
                log_message(f"--- {category} ---")
                last_category = category
            value = all_topic_values[topic]
            count = all_topic_counts.get(topic, 0)
            # Temperatur direkt lesbar machen
            if "Temperature" in topic and value.isdigit():
                value = f"{int(value)/10:.1f}°C (raw={value})"
            log_message(f"{index:03d}. {topic}  | last={value}  | count={count}")

        if DISCOVERY_CSV:
            try:
                discovery_dir = os.path.dirname(DISCOVERY_CSV)
                if discovery_dir:
                    os.makedirs(discovery_dir, exist_ok=True)
                with open(DISCOVERY_CSV, "w", newline="", encoding="utf-8") as csv_file:
                    writer = csv.writer(csv_file)
                    writer.writerow(["topic", "category", "last", "count"])
                    for topic in sorted(all_topic_values.keys()):
                        parts = topic.split("/")
                        category = parts[2] if len(parts) > 2 else ""
                        value = all_topic_values[topic]
                        if "Temperature" in topic and value.isdigit():
                            value = f"{int(value)/10:.1f}°C"
                        writer.writerow([
                            topic,
                            category,
                            value,
                            all_topic_counts.get(topic, 0),
                        ])
                log_message(f"CSV-Export: {DISCOVERY_CSV}")
            except OSError as error:
                log_message(f"CSV-Export fehlgeschlagen: {error}")

        log_message(f"")
        log_message(f"{'='*80}")
        status_count = len(status_topic_values)
        other_count = len(all_topic_values) - status_count
        log_message(f"Gesamt: {len(all_topic_values)} Topics ({status_count} STATUS, {other_count} andere)")
        log_message(f"{'='*80}")
        return 0

    if MODE == "temp":
        log_message(
            "Temperatur-Ansicht aktiv: warte auf Tool1/Temperature/Read und Tool2/Temperature/Read "
            f"(Hinweis alle {LIVE_IDLE_WARN_SECONDS}s)"
        )
        client.loop_start()
        try:
            last_hint_at = time.monotonic()
            while True:
                time.sleep(1)
                now_monotonic = time.monotonic()
                if now_monotonic - last_hint_at >= LIVE_IDLE_WARN_SECONDS:
                    since_start = (datetime.now() - start_time).total_seconds()
                    if last_temp_topic_at is None:
                        log_message(f"⏳ Keine Temperatur-Topics seit Start ({since_start:.0f}s).")
                    else:
                        idle_seconds = (datetime.now() - last_temp_topic_at).total_seconds()
                        log_message(
                            f"⏳ Letztes Temperatur-Topic vor {idle_seconds:.0f}s, "
                            f"gesamt Temperatur-Meldungen: {temp_message_count}."
                        )
                    last_hint_at = now_monotonic
        except KeyboardInterrupt:
            elapsed = (datetime.now() - start_time).total_seconds()
            log_message("")
            log_message(f"{'='*80}")
            log_message("Temperatur-Monitor beendet")
            log_message(f"{'='*80}")
            log_message(f"Laufzeit            : {elapsed:.1f}s")
            log_message(f"Nachrichten gesamt  : {message_count}")
            log_message(f"Temperatur-Meldungen: {temp_message_count}")
            log_message(f"Fehler              : {error_count}")
            if message_count > 0 and elapsed > 0:
                log_message(f"Durchsatz           : {message_count / elapsed:.2f} Msg/s")
            log_message(f"{'='*80}")
            client.loop_stop()
            client.disconnect()
        return 0

    if MODE == "live":
        log_message(
            f"Live-Ansicht aktiv: warte auf Temperature/Read, Power/Read, Counter/Time, ONLINE, State "
            f"(Hinweis alle {LIVE_IDLE_WARN_SECONDS}s)"
        )
        client.loop_start()
        try:
            last_hint_at = time.monotonic()
            while True:
                time.sleep(1)
                now_monotonic = time.monotonic()
                if now_monotonic - last_hint_at >= LIVE_IDLE_WARN_SECONDS:
                    since_start = (datetime.now() - start_time).total_seconds()
                    if last_live_topic_at is None:
                        log_message(
                            f"⏳ Keine Live-Topics seit Start ({since_start:.0f}s). "
                            "Station sendet aktuell nur statische STATUS-Daten."
                        )
                    else:
                        idle_seconds = (datetime.now() - last_live_topic_at).total_seconds()
                        log_message(
                            f"⏳ Letztes Live-Topic vor {idle_seconds:.0f}s, "
                            f"gesamt Live-Meldungen: {live_message_count}."
                        )
                    last_hint_at = now_monotonic
        except KeyboardInterrupt:
            elapsed = (datetime.now() - start_time).total_seconds()
            log_message("")
            log_message(f"{'='*80}")
            log_message("Live-Monitor beendet")
            log_message(f"{'='*80}")
            log_message(f"Laufzeit      : {elapsed:.1f}s")
            log_message(f"Nachrichten   : {message_count}")
            log_message(f"Live-Meldungen: {live_message_count}")
            log_message(f"Fehler        : {error_count}")
            if message_count > 0 and elapsed > 0:
                log_message(f"Durchsatz     : {message_count / elapsed:.2f} Msg/s")
            log_message(f"{'='*80}")
            client.loop_stop()
            client.disconnect()
        return 0

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        elapsed = (datetime.now() - start_time).total_seconds()
        log_message("")
        log_message(f"{'='*80}")
        log_message(f"Monitor beendet")
        log_message(f"{'='*80}")
        log_message(f"Laufzeit      : {elapsed:.1f}s")
        log_message(f"Nachrichten   : {message_count}")
        log_message(f"Fehler        : {error_count}")
        if message_count > 0:
            log_message(f"Durchsatz     : {message_count / elapsed:.2f} Msg/s")
        log_message(f"{'='*80}")
        client.disconnect()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())