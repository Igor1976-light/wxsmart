# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false
from typing import Any
import json

import paho.mqtt.client as mqtt


def on_connect(client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any = None) -> None:
    print("Connected with result code", reason_code)
    client.subscribe("#")


def on_message(client: Any, userdata: Any, msg: Any) -> None:
    payload_text: str = msg.payload.decode(errors="replace")
    try:
        data: Any = json.loads(payload_text)
        print(f"{msg.topic}: {data}")
    except json.JSONDecodeError:
        print(f"{msg.topic}: {payload_text}")


client: Any = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    transport="websockets",
)
client.on_connect = on_connect
client.on_message = on_message

client.connect("localhost", 9001, 60)
client.loop_forever()