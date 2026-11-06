# DIY Door Alarm

A door alarm written in MicroPython. A camera unit near the door reads a reed switch on the door, tells a separate alarm unit to play a sound through a speaker, and emails you a snapshot.

The two units talk directly over ESP-NOW, so the alarm itself doesn't depend on the internet. Only the email needs WiFi.

```
[door] --reed switch, 3 m cable--> [ESP32-CAM camera] --ESP-NOW--> [ESP32-C3 alarm] --UART--> [MP3 module] --> [speaker]
                                           |
                                           +--WiFi/SMTP--> [your inbox]
```

| Unit | Board | Job |
|---|---|---|
| Camera | AI-Thinker ESP32-CAM | Watches the reed switch, sends door events to the alarm, emails a photo when the door opens |
| Alarm | ESP32-C3 SuperMini | Plays the sound while the door is open |

Door events go to the alarm before the photo is taken. If the camera or WiFi fails, the camera unit keeps working as a door sensor without photos.

## Getting started

1. Buy the parts and wire each unit: [docs/hardware.md](docs/hardware.md)
2. Flash MicroPython and copy the code to each board: [docs/setup.md](docs/setup.md)
3. If something doesn't work: [docs/troubleshooting.md](docs/troubleshooting.md)

## Project layout

```
firmware/
  config.example.py     Template for config.py: alarm MAC address and channel
  common/door_link.py   ESP-NOW helpers and message format, used by both units
  alarm/main.py         Alarm unit
  alarm/dfplayer.py     MP3 module driver
  camera/main.py        Camera unit
  camera/smtp_mail.py   Sends the email
  camera/bmp.py         Converts camera frames to BMP images
  camera/camera_secrets.example.py   Template for WiFi and email credentials
tools/camup.py          Copies files to the ESP32-CAM where mpremote can't
docs/                   Hardware, setup and troubleshooting guides
prototype-draft/        The original design document
```

## Possible extensions

- More reed switches on the camera unit's free pins, such as GPIO14, for other doors or windows
- A silence or disarm button on the alarm unit
- Phone notifications or remote control over WiFi and MQTT or HTTP
- Saving snapshots to the camera unit's microSD card as a backup to email. This would need the reed switch moved off GPIO13, which the card uses.
- Short video clips instead of a single photo, within your email provider's attachment limit
- A cooldown so that repeated door events don't each send an email
