# DIY Door Alarm

A wireless door alarm written in MicroPython. A sensor unit on the door tells a separate alarm unit to play a sound through a speaker. An optional camera unit emails you a snapshot each time the door opens.

The units talk directly over ESP-NOW, so the alarm works without a router or internet connection. Only the camera unit needs WiFi, to send its email.

```
                                     +--ESP-NOW--> [ESP32-C3 alarm] --UART--> [MP3 module] --> [speaker]
[door] --reed switch--> [ESP32-C3 sensor]
                                     +--ESP-NOW--> [ESP32-CAM camera] --WiFi/SMTP--> [your inbox]
```

| Unit | Board | Job |
|---|---|---|
| Sensor | ESP32-C3 SuperMini | Watches the reed switch and sends door events |
| Alarm | ESP32-C3 SuperMini | Plays the sound while the door is open |
| Camera (optional) | AI-Thinker ESP32-CAM | Emails a photo when the door opens |

The camera has its own board because the ESP32-C3 has no camera interface.

## Getting started

1. Buy the parts and wire each unit: [docs/hardware.md](docs/hardware.md)
2. Flash MicroPython and copy the code to each board: [docs/setup.md](docs/setup.md)
3. If something doesn't work: [docs/troubleshooting.md](docs/troubleshooting.md)

## Project layout

```
firmware/
  config.example.py     Template for config.py: MAC addresses and channel
  common/door_link.py   ESP-NOW helpers and message format, used by every unit
  sensor/main.py        Sensor unit
  alarm/main.py         Alarm unit
  alarm/dfplayer.py     MP3 module driver
  camera/main.py        Camera unit
  camera/smtp_mail.py   Sends the email
  camera/camera_secrets.example.py   Template for WiFi and email credentials
docs/                   Hardware, setup and troubleshooting guides
prototype-draft/        The original design document
```

## Possible extensions

- Several sensor units, one per door or window, reporting to one alarm unit
- A silence or disarm button on the alarm unit
- Phone notifications or remote control over WiFi and MQTT or HTTP
- Saving snapshots to the camera unit's microSD card as a backup to email
- Short video clips instead of a single photo, within your email provider's attachment limit
- A cooldown so that repeated door events don't each send an email
- Deep sleep with wake-on-pin on the sensor unit for longer battery life
