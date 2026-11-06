# Troubleshooting

## Door and alarm

| Symptom | What to check |
|---|---|
| Alarm plays when the door closes instead of opens | Change `DOOR_OPEN_LEVEL` in [camera/main.py](../firmware/camera/main.py) |
| Double triggers or false alarms | The long cable is picking up interference, or the switch is chattering. Check the external pull-up and the 100 nF capacitor at the board end (see [hardware.md](hardware.md#camera-unit)), then try increasing `DEBOUNCE_MS`. |
| Camera prints "not acknowledged by alarm" | Check `ALARM_MAC`, that both units have the same `config.py`, and the distance between them |
| Alarm never reacts, but the camera prints door events | `ESPNOW_CHANNEL` doesn't match the router's channel. The camera prints a warning once it joins WiFi if it is wrong. |
| Worked before, then the alarm stopped reacting | The router probably changed channel. Fix its channel in the router settings. |
| "MP3 module did not respond" | Check that TX and RX aren't swapped, the module's power, and that the SD card is inserted and FAT32 |
| Module responds but plays nothing | Check the speaker wiring and that the card has an MP3 file in its root |
| Commands have no effect at all | Your module may not use the DFPlayer command set. Check the seller's manual and adjust [dfplayer.py](../firmware/alarm/dfplayer.py). |
| Unreliable range | Move the alarm unit closer, or add an ESP-NOW repeater node |

## Camera and email

| Symptom | What to check |
|---|---|
| Camera board doesn't start after wiring the reed switch | The switch is on GPIO12 or another boot pin. Use GPIO13. |
| Random reboots or failed captures | The power supply is too weak. Use a proper 5 V / 2 A supply rather than a USB hub. |
| "running without photos" | The camera failed to start twice in a row. Check the camera ribbon cable and power, then reset the board. |
| "No WiFi: skipping snapshot" | Check the WiFi details in `camera_secrets.py` and the signal at the camera's location |
| `ImportError: no module named 'camera'` | The board is running standard MicroPython rather than the camera firmware |
| `Snapshot failed` with an SMTP error | Check the sender address and app password. Gmail needs 2-Step Verification enabled, and the 16-character password entered without spaces. |
| `Snapshot failed` with a memory error | Try a smaller `FRAME_SIZE` in [camera/main.py](../firmware/camera/main.py) |

## Known limitations

- **The camera unit doesn't watch the door while it sends an email,** which takes a few seconds. A door that closes in that time is reported once the email is done, so the alarm may run a few seconds longer. A door that closes and reopens in that time gets no second photo.
- **A lost ESP-NOW packet is retried only briefly.** If the alarm doesn't acknowledge after three tries, that door event produces no alarm.
- **Credentials are stored as plain text on the camera board.** Anyone with physical access can read `camera_secrets.py` over the serial port, so use an app password you can revoke and a dedicated email account if possible. They are kept off the alarm board.
- **The email server's TLS certificate isn't verified,** so the connection is encrypted but the server's identity isn't checked.
- **Email providers may flag frequent automated messages.** Each door opening sends one email, so a busy door could trigger this. A cooldown is listed as a possible extension in the [README](../README.md).
- **An unexpected error stops a unit until it is reset,** because MicroPython then drops to its prompt instead of restarting the program.
