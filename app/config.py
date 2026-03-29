from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    mqtt_host: str = os.getenv("MQTT_HOST", "localhost")
    mqtt_port: int = int(os.getenv("MQTT_PORT", "9001"))
    mqtt_topic: str = os.getenv("MQTT_TOPIC", "WXSMART/#")
    mqtt_transport: str = os.getenv("MQTT_TRANSPORT", "websockets")
    mqtt_keepalive: int = int(os.getenv("MQTT_KEEPALIVE", "60"))

    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    app_reload: bool = os.getenv("APP_RELOAD", "0").lower() in ("1", "true", "yes")

    # --- InfluxDB 2 (optional) ---
    # Wird nicht geschrieben wenn influx_url leer ist
    influx_url: str = os.getenv("INFLUX_URL", "")
    influx_token: str = os.getenv("INFLUX_TOKEN", "")
    influx_org: str = os.getenv("INFLUX_ORG", "wxsmart")
    influx_bucket: str = os.getenv("INFLUX_BUCKET", "soldering")


settings = Settings()
