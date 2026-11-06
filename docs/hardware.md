# Hardware

## Parts

### Camera unit

Watches the door through the reed switch, tells the alarm unit, and emails a photo.

- AI-Thinker ESP32-CAM with OV2640 camera. The MicroPython camera driver requires a board with PSRAM, which this one has.
- USB-to-serial (FTDI) adapter, because the board has no USB port of its own
- 5 V / 2 A power supply. Camera and WiFi together draw more than the alarm unit.
- Magnetic reed switch (door/window type)
- About 3 m of two-core cable, ideally twisted pair, for the reed switch
- 4.7–10 kΩ resistor (pull-up)
- 100 nF ceramic capacitor
- 1 kΩ resistor (optional, protects the pin from static on the long cable)
- Home WiFi network
- An email account with an app password

ESP-NOW packets are limited to about 250 bytes, too small for a photo. That is why this unit also needs regular WiFi.

### Alarm unit

- ESP32-C3 SuperMini (16-pin, USB-C)
- UART MP3 player module with an onboard mono amplifier and speaker terminal. It must use the DFPlayer Mini command set, so check the seller's specification.
- microSD card, formatted as FAT32
- Speaker, 3 W at 4 Ω or 8 Ω. Check your module's amplifier rating; many are similar to the DFPlayer Mini at about 3 W into 4 Ω.
- 1 kΩ resistor for the module's RX line

## Wiring

### Camera unit

The camera ships attached to the board. Wire the reed switch like this:

```
3.3V ──[4.7–10 kΩ]──┐
                    ├──[1 kΩ, optional]──── 3 m cable ──── reed switch ──┐
GPIO13 ─────────────┤                                                    │
                    └──[100 nF]── GND                                    │
GND ──────────────────────────────── 3 m cable ──────────────────────────┘
```

| Reed switch | ESP32-CAM |
|---|---|
| Leg 1 | GPIO13 (with the pull-up to 3.3 V and the capacitor to GND at the board end) |
| Leg 2 | GND |

The legs are interchangeable. Put the resistor and capacitor next to the board, not at the switch.

The chip's internal pull-up alone is too weak for a 3 m cable: the cable picks up interference, especially from the board's own WiFi, which can cause false alarms. The external pull-up and the capacitor keep the line steady, and the code's 50 ms debounce handles the rest.

The code assumes the switch is closed while the magnet is near, so an open door reads high. If yours works the other way round, change `DOOR_OPEN_LEVEL` in [camera/main.py](../firmware/camera/main.py).

**Why GPIO13:** most of the ESP32-CAM's pins go to the camera, PSRAM and the SD card slot. The SD card pins are free because the code doesn't use the card. GPIO13 is one of them and isn't read by the chip at boot. GPIO14 also works. Avoid these:

- **GPIO12:** if it is pulled high at power-on, the chip sets the wrong flash voltage and won't start.
- **GPIO0 and GPIO2:** read at boot to choose the boot mode.
- **GPIO4:** drives the flash LED.
- **GPIO16:** used by the PSRAM.
- **GPIO1 and GPIO3:** the serial port used for flashing and the monitor.

For flashing and copying files, connect the FTDI adapter:

| FTDI | ESP32-CAM |
|---|---|
| TX | U0R |
| RX | U0T |
| GND | GND |
| VCC | 5V |

To flash firmware, also connect **GPIO0 to GND** before powering on. Remove that jumper and power-cycle for normal use, including when copying the Python files.

### ESP32-C3 SuperMini pins

| Side | Pins |
|---|---|
| One side | 5V, G, 3.3V, GPIO4, GPIO3, GPIO2, GPIO1, GPIO0 |
| Other side | GPIO5, GPIO6, GPIO7, GPIO8, GPIO9, GPIO10, GPIO20, GPIO21 |

### Alarm unit

| MP3 module | ESP32-C3 |
|---|---|
| VCC | 5V (some modules accept 3.3 V, so check yours) |
| GND | G |
| RX | GPIO21, through the 1 kΩ resistor |
| TX | GPIO20 |

Connect the speaker to the module's SPK+ / SPK- terminal, which may be labeled SPK_1 / SPK_2.
