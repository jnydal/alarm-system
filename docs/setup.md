# Setup

Run these commands from the project root. Replace `COM5` (alarm unit) and `COM6` (camera unit) with your boards' ports, which you can find with `py -m mpremote connect list`.

## 1. Install the tools

```powershell
py -m pip install esptool mpremote
```

## 2. Create your config and credentials

```powershell
Copy-Item firmware\config.example.py firmware\config.py
Copy-Item firmware\camera\camera_secrets.example.py firmware\camera\camera_secrets.py
```

Fill in `camera_secrets.py` with your WiFi and email details. For Gmail you need an app password, because regular account passwords don't work for this kind of SMTP login: turn on 2-Step Verification, then go to Google Account > Security > 2-Step Verification > App Passwords.

You'll fill in `config.py` in the steps below.

## 3. Set up the alarm unit

**Flash MicroPython.** Download the latest `.bin` for [ESP32_GENERIC_C3](https://micropython.org/download/ESP32_GENERIC_C3/), then run:

```powershell
py -m esptool --chip esp32c3 --port COM5 erase_flash
py -m esptool --chip esp32c3 --port COM5 write_flash -z 0x0 ESP32_GENERIC_C3-<version>.bin
```

If the board isn't detected, hold BOOT, tap RESET, then release BOOT, and try again.

**Prepare the SD card.** Format it as FAT32 and copy your alarm sound to the root as `0001.mp3`. Keep it the only file on the card, because the module picks tracks by their position on the card, not by name. Insert the card before powering on.

**Wire the MP3 module.** Unplug the board first, then connect:

| MP3 module | ESP32-C3 |
|---|---|
| VCC | 5V (some modules accept 3.3 V, so check yours) |
| GND | G |
| RX | GPIO21, through a 1 kΩ resistor |
| TX | GPIO20 |

RX and TX cross over: the module's RX receives from the board's transmit pin (GPIO21), and its TX sends to the board's receive pin (GPIO20). Connect the speaker to the module's SPK+ / SPK- terminal, which may be labeled SPK_1 / SPK_2. Plug the board back in when you're done.

**Copy the code and read the MAC address:**

```powershell
py -m mpremote connect COM5 cp firmware/config.py firmware/common/door_link.py firmware/alarm/dfplayer.py firmware/alarm/main.py : + reset
py -m mpremote connect COM5 repl
```

The unit prints its MAC address every 10 seconds. Put it in `ALARM_MAC` in `firmware/config.py`. Press Ctrl+] to leave the monitor.

## 4. Set up the camera unit

**1. Wire the reed switch.** Unplug the board first. See [hardware.md](hardware.md#camera-unit) for the full wiring, including the pull-up resistor and capacitor that the 3 m cable needs. In short:

| Reed switch | ESP32-CAM |
|---|---|
| Leg 1 | GPIO13 |
| Leg 2 | GND |

**2. Flash the camera firmware.** Standard MicroPython has no camera driver, so download an image for a plain ESP32 with PSRAM from the [micropython-camera-API releases](https://github.com/cnadler86/micropython-camera-API/releases). With GPIO0 connected to GND, power on the board and run:

```powershell
py -m esptool --chip esp32 --port COM6 erase_flash
py -m esptool --chip esp32 --port COM6 write_flash -z 0x1000 <downloaded-image>.bin
```

Check the release notes in case they give a different flash offset. Then remove the GPIO0 jumper and power-cycle the board.

**3. Copy the code and read the router channel.** On boards with an ESP32-CAM USB adapter, `mpremote` fails with "could not enter raw repl", because the adapter holds the chip in reset while mpremote has the port open. Use `tools/camup.py` instead for this board. It does the same job, and needs no extra install because `pyserial` comes with `esptool`:

```powershell
py tools/camup.py COM6 firmware/config.py firmware/common/door_link.py firmware/camera/camera_secrets.py firmware/camera/smtp_mail.py firmware/camera/bmp.py firmware/camera/main.py --monitor
```

Note the printed **router channel**, then press Ctrl+C to stop the monitor. If your board works with `mpremote`, you can use the usual `cp ... : + reset` and `repl` commands instead.

**4. Set the channel.** Set `ESPNOW_CHANNEL` in `firmware/config.py` to the router channel, then copy `config.py` to both boards:

```powershell
py -m mpremote connect COM5 cp firmware/config.py : + reset
py tools/camup.py COM6 firmware/config.py --reset
```

**5. Fix your router's channel.** In its settings, change the 2.4 GHz channel from "auto" to the fixed number you noted. If the router moves to another channel, the camera follows it and the alarm stops hearing it.

## 5. Test on the bench

Power both boards and move the magnet away from the reed switch. The alarm should play straight away, and an email with the photo should arrive within a few seconds. The alarm should stop when you bring the magnet back. To see what each unit is doing, open its monitor with `py -m mpremote connect COM5 repl` or `py tools/camup.py COM6 --monitor`.

## 6. Mount the units

- **Camera:** mount it with a view of the door, within reach of the 3 m reed switch cable, on a stable 5 V supply. Fix the reed switch to the door frame and the magnet to the door, a few millimeters apart when closed.
- **Alarm:** place it where you want to hear the sound. Expect about 30 to 50 m of range indoors through a wall or two.
