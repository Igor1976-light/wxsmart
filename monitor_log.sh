#!/bin/bash

# Live-Tail der MQTT-Log-Datei mit farblicher Hervorhebung
# Verwendung: ./monitor_log.sh [optional: pfad/zur/log-datei]

LOG_FILE="${1:-wxsmart_messages.log}"

if [ ! -f "$LOG_FILE" ]; then
    echo "❌ Log-Datei nicht gefunden: $LOG_FILE"
    echo "Starte zuerst den Monitor mit: python wxsmart_2.py"
    exit 1
fi

echo "📊 Live-Monitoring: $LOG_FILE"
echo "Drücke Ctrl+C zum Beenden"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Highlight-Farben
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m' # No Color

tail -f "$LOG_FILE" | while IFS= read -r line; do
    # Nachrichten-Header hervorheben
    if [[ $line =~ "Nachricht #" ]]; then
        echo -e "${BOLD}${GREEN}$line${NC}"
    # Fehler hervorheben
    elif [[ $line =~ "FEHLER" ]] || [[ $line =~ "✖" ]]; then
        echo -e "${RED}$line${NC}"
    # Verbindungs-Status
    elif [[ $line =~ "✔" ]] || [[ $line =~ "Verbunden" ]]; then
        echo -e "${GREEN}$line${NC}"
    # JSON-Ausgabe
    elif [[ $line =~ "JSON" ]] || [[ $line =~ "{" ]]; then
        echo -e "${CYAN}$line${NC}"
    # Normale Ausgabe
    else
        echo "$line"
    fi
done
