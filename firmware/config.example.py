# Settings for the ESP-NOW link. Copy this file to firmware/config.py and edit it.

# Printed by the alarm unit over USB once it is running.
ALARM_MAC = "00:00:00:00:00:00"

# The channel the sensor and alarm units stay on. Without the camera unit, any
# channel from 1 to 13 works. With it, this must equal your router's channel,
# which the camera unit prints when it connects.
ESPNOW_CHANNEL = 1

# Set to True to make the sensor unit also notify the camera unit.
CAMERA_ENABLED = False

# Printed by the camera unit once it is running.
CAMERA_MAC = "00:00:00:00:00:00"
