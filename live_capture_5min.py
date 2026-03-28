import os
import time
from datetime import datetime
from typing import Any

import paho.mqtt.client as mqtt

DURATION_SECONDS = int(os.getenv("WXSMART_CAPTURE_SECONDS", "45"))
DEVICE_PREFIX = os.getenv("WXSMART_CAPTURE_DEVICE_PREFIX", "WXSMART/")
BROKER_HOST = os.getenv("MQTT_HOST", "localhost")
BROKER_PORT = 9001
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOG_FILE = os.path.join(PROJECT_DIR, "temp", "wxsmart_live_5min.log")
LOG_FILE = os.getenv("WXSMART_CAPTURE_LOG", DEFAULT_LOG_FILE)


def now() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


def log_line(message: str) -> None:
    print(message, flush=True)
    if LOG_FILE:
        log_dir = os.path.dirname(LOG_FILE)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(message + "\n")

def on_connect(
    client: mqtt.Client,
    userdata: Any,
    flags: dict[str, Any],
    rc: int,
) -> None:
    client.subscribe("WXSMART/#", qos=0)
    log_line(f"[{now()}] connected rc={rc}")


def on_message(client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
    topic = msg.topic
    if not topic.startswith(DEVICE_PREFIX):
        return
    payload = msg.payload.decode("utf-8", errors="replace").strip()

    if "Temperature" in topic and payload.isdigit():
        payload = f"{int(payload)/10.0:.1f}°C"
    elif "Power" in topic and payload.isdigit():
        payload = f"{int(payload)/10.0:.1f}W"

    log_line(f"[{now()}] {topic} = {payload}")


def main() -> None:
    if LOG_FILE:
        log_dir = os.path.dirname(LOG_FILE)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

    client = mqtt.Client(
        transport="websockets",
    )
    client.on_message = on_message
    client.connect(BROKER_HOST, BROKER_PORT, 60)
    client.loop_start()
    time.sleep(DURATION_SECONDS)
    client.loop_stop()
    client.disconnect()
    log_line(f"[{now()}] done")


if __name__ == "__main__":
    main()