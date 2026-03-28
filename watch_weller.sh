#!/bin/bash

# Kontinuierliche Weller-Überwachung: Prüft jede Sekunde, ob Port 9001 offen wird

WELLER_IP="192.168.1.128"
CHECK_PORT=9001
MAX_ATTEMPTS=120  # 2 Minuten

echo "🔎 Weller-Monitor: Prüfe auf offenen Port $CHECK_PORT alle 1 Sek..."
echo "Lötstation jetzt an/aus schalten oder neustarten!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

attempt=0
found=false

while [ $attempt -lt $MAX_ATTEMPTS ]; do
    attempt=$((attempt + 1))
    timestamp=$(date "+%H:%M:%S")
    
    # Ping-Test
    if ping -c 1 -W 1 "$WELLER_IP" &>/dev/null; then
        ping_status="✅ ONLINE"
    else
        ping_status="❌ OFFLINE"
    fi
    
    # Port-Test
    if timeout 1 bash -c "echo > /dev/tcp/$WELLER_IP/$CHECK_PORT" 2>/dev/null; then
        echo "[$timestamp] $ping_status | Port $CHECK_PORT: 🟢 OFFEN!"
        echo "              → Weller sendet jetzt Daten an Broker!"
        found=true
        break
    else
        if [ $((attempt % 10)) -eq 0 ]; then
            echo "[$timestamp] $ping_status | Port $CHECK_PORT: 🔴 Zu ($attempt/$MAX_ATTEMPTS)"
        fi
    fi
    
    sleep 1
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ "$found" = true ]; then
    echo "✅ Weller hat sich gemeldet!"
    echo "   Überprüfe das Monitor-Log: tail -f monitor_live.log"
else
    echo "❌ Weller hat sich nicht gemeldet ($MAX_ATTEMPTS Sek gewartet)"
    echo ""
    echo "Mögliche Lösungen:"
    echo "1. Weller ist im Standby → Einschalten/Aufwecken"
    echo "2. Netzwerk-Modul ist nicht aktiv → In Weller-Einstellungen aktivieren"
    echo "3. Falsche MQTT-Konfiguration → Broker-IP 192.168.1.247 / Port 9001 prüfen"
    echo "4. Weller-Reboot → Ausschalten für 10 Sekunden, dann anschalten"
fi
echo ""
