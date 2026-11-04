# Troubleshooting

## Sensor and alarm

| Symptom | What to check |
|---|---|
| Alarm plays when the door closes instead of opens | Change `DOOR_OPEN_LEVEL` in [sensor/main.py](../firmware/sensor/main.py) |
| Double triggers | The reed switch is chattering. Increase `DEBOUNCE_MS` in the same file. |
| Sensor prints "not acknowledged" | Check `ALARM_MAC`, that both units have the same `config.py`, and the distance between them |
| "MP3 module did not respond" | Check that TX and RX aren't swapped, the module's power, and that the SD card is inserted and FAT32 |
| Module responds but plays nothing | Check the speaker wiring and that the card has an MP3 file in its root |
| Commands have no effect at all | Your module may not use the DFPlayer command set. Check the seller's manual and adjust [dfplayer.py](../firmware/alarm/dfplayer.py). |
| Unreliable range | Move the alarm unit closer, or add an ESP-NOW repeater node |

## Camera unit

| Symptom | What to check |
|---|---|
| Random reboots or failed captures | The power supply is too weak. Use a proper 5 V / 2 A supply rather than a USB hub. |
| Never reacts to the door | The sensor's channel doesn't match the router's. The camera prints a warning at startup if `ESPNOW_CHANNEL` is wrong. |
| Worked before, then stopped reacting | The router probably changed channel. Fix its channel in the router settings. |
| `ImportError: no module named 'camera'` | The board is running standard MicroPython rather than the camera firmware |
| `Snapshot failed` with an SMTP error | Check the sender address and app password. Gmail needs 2-Step Verification enabled, and the 16-character password entered without spaces. |
| `Snapshot failed` with a memory error | Try a smaller `frame_size` in [camera/main.py](../firmware/camera/main.py) |

## Known limitations

- **A lost ESP-NOW packet is not re-sent.** The sensor reports a failed delivery but doesn't retry, so that door event produces no alarm.
- **The camera must stay connected to WiFi** to hear door events. While it is reconnecting, it can miss them.
- **The camera unit stops listening while it sends an email.** Events that arrive in that time wait in a small buffer, and any that overflow it are lost.
- **Credentials are stored as plain text on the camera board.** Anyone with physical access can read `camera_secrets.py` over the serial port, so use an app password you can revoke and a dedicated email account if possible. They are kept off the other two boards.
- **The email server's TLS certificate isn't verified,** so the connection is encrypted but the server's identity isn't checked.
- **Email providers may flag frequent automated messages.** Each door opening sends one email, so a busy door could trigger this. A cooldown is listed as a possible extension in the [README](../README.md).
- **An unexpected error stops a unit until it is reset,** because MicroPython then drops to its prompt instead of restarting the program.
