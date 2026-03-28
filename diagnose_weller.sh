#!/bin/bash

# Diagnose-Script: Prüft Weller-Erreichbarkeit und MQTT-Ports

WELLER_IP="${WELLER_IP:-192.168.0.50}"
BROKER_IP="${BROKER_IP:-127.0.0.1}"

echo "🔍 WXSMART/Weller Diagnose"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 1. Ping-Test
echo "1️⃣  Weller erreichbar? ($WELLER_IP)"
if ping -c 1 -W 2 "$WELLER_IP" &>/dev/null; then
    echo "   ✅ ONLINE"
else
    echo "   ❌ OFFLINE oder nicht erreichbar"
    echo "   Hinweis: Lötstation ausgeschaltet oder falsche IP?"
    exit 1
fi

echo ""
echo "2️⃣  MQTT-Ports auf Weller:"

# Standard MQTT (1883)
echo -n "   Port 1883 (Standard MQTT): "
if timeout 2 bash -c "echo > /dev/tcp/$WELLER_IP/1883" 2>/dev/null; then
    echo "✅ OFFEN"
else
    echo "❌ Zu"
fi

# WebSocket MQTT (9001)
echo -n "   Port 9001 (WebSocket):    "
if timeout 2 bash -c "echo > /dev/tcp/$WELLER_IP/9001" 2>/dev/null; then
    echo "✅ OFFEN"
else
    echo "❌ Zu"
fi

# Andere häufige MQTT-Ports
echo -n "   Port 8883 (MQTT+TLS):     "
if timeout 2 bash -c "echo > /dev/tcp/$WELLER_IP/8883" 2>/dev/null; then
    echo "✅ OFFEN"
else
    echo "❌ Zu"
fi

echo ""
echo "3️⃣  Broker-Status ($BROKER_IP):"
echo -n "   Port 9001 (WebSocket):    "
if timeout 2 bash -c "echo > /dev/tcp/$BROKER_IP/9001" 2>/dev/null; then
    echo "✅ ERREICHBAR (Broker läuft)"
else
    echo "❌ Nicht erreichbar (Broker nicht aktiv?)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 Nächste Schritte:"
echo "   1. Überprüfe die Weller-Konfiguration:"
echo "      - Broker-Host: $BROKER_IP"
echo "      - Broker-Port: 9001"
echo "      - Protokoll: WebSocket MQTT (oder Standard MQTT auf 1883)"
echo ""
echo "   2. Wenn Weller nur Standard MQTT kann (1883):"
echo "      - Starte Broker mit TCP-Listener: mosquitto -c /opt/homebrew/etc/mosquitto/mosquitto.conf"
echo "      - Und ergänze in mosquitto.conf:"
echo "        listener 1883"
echo "        protocol mqtt"
echo ""
