# Settings for the ESP-NOW link. Copy this file to firmware/config.py and edit it.

# Printed by the alarm unit over USB once it is running.
ALARM_MAC = "00:00:00:00:00:00"

# The channel the alarm unit stays on. It must equal your router's channel,
# because the camera unit follows the router once it joins WiFi. The camera
# unit prints the router's channel when it connects.
ESPNOW_CHANNEL = 1
