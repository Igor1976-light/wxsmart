# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false
from datetime import datetime
import json
import os
import sys
from typing import Any

import paho.mqtt.client as mqtt


BROKER_HOST = os.getenv("MQTT_HOST", "localhost")
BROKER_PORT = 9001
TOPIC_FILTER = os.getenv("MQTT_TOPIC", "WXSMART/#")
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOG_FILE = os.path.join(PROJECT_DIR, "temp", "wxsmart_messages.log")
LOG_FILE = os.getenv("MQTT_LOG_FILE", DEFAULT_LOG_FILE)
DEFAULT_TEMP_LOG_FILE = os.path.join(PROJECT_DIR, "temp", "wxsmart_temperature.log")
TEMP_LOG_FILE = os.getenv("MQTT_TEMP_LOG_FILE", DEFAULT_TEMP_LOG_FILE)
VERBOSE = os.getenv("MQTT_VERBOSE", "1").lower() in ("1", "true", "yes")
COMPACT_VIEW = os.getenv("MQTT_COMPACT", "1").lower() in ("1", "true", "yes")
TEMP_ONLY = os.getenv("MQTT_TEMP_ONLY", "1").lower() in ("1", "true", "yes")

message_count = 0
error_count = 0
start_time = datetime.now()


def is_temperature_topic(topic: str) -> bool:
    return (
        "/STATUS/Tool1/Temperature/Read" in topic
        or "/STATUS/Tool2/Temperature/Read" in topic
    )


def write_temperature_log(msg: str) -> None:
    if not TEMP_LOG_FILE:
        return
    try:
        temp_log_dir = os.path.dirname(TEMP_LOG_FILE)
        if temp_log_dir:
            os.makedirs(temp_log_dir, exist_ok=True)
        with open(TEMP_LOG_FILE, "a", encoding="utf-8") as file_handle:
            file_handle.write(msg + "\n")
    except OSError as error:
        print(f"[TEMP_LOG_ERROR] Datei schreiben fehlgeschlagen: {error}", file=sys.stderr)


def log_message(msg: str) -> None:
    """Gibt Nachricht auf Stdout und optional in Datei aus."""
    print(msg, flush=True)
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
    global message_count, error_count
    message_count += 1

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    elapsed = (datetime.now() - start_time).total_seconds()
    payload_bytes = bytes(msg.payload)
    payload_text = payload_bytes.decode("utf-8", errors="replace")
    payload_value = parse_payload_value(payload_text)

    if TEMP_ONLY and not is_temperature_topic(msg.topic):
        return

    if COMPACT_VIEW:
        line = format_compact_line(msg.topic, payload_value, timestamp, message_count)
        log_message(line)
        if is_temperature_topic(msg.topic):
            write_temperature_log(line)
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
    log_message(f"Temp-Only  : {TEMP_ONLY} (Tool1+Tool2 Temperature/Read)")
    log_message(f"Start-Zeit : {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    log_message(f"{'='*80}")
    log_message("")

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