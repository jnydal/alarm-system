# Hardware

## Parts

### Sensor unit

- ESP32-C3 SuperMini (16-pin, USB-C)
- Magnetic reed switch (door/window type)
- USB power, or a LiPo battery and charging board for wireless operation

The code uses the chip's internal pull-up, so no external resistor is needed.

### Alarm unit

- ESP32-C3 SuperMini
- UART MP3 player module with an onboard mono amplifier and speaker terminal. It must use the DFPlayer Mini command set, so check the seller's specification.
- microSD card, formatted as FAT32
- Speaker, 3 W at 4 Ω or 8 Ω. Check your module's amplifier rating; many are similar to the DFPlayer Mini at about 3 W into 4 Ω.
- 1 kΩ resistor for the module's RX line

### Camera unit (optional)

- AI-Thinker ESP32-CAM with OV2640 camera. The MicroPython camera driver requires a board with PSRAM, which this one has.
- USB-to-serial (FTDI) adapter, because the board has no USB port of its own
- 5 V / 2 A power supply. Camera and WiFi together draw more than the other units.
- Home WiFi network
- An email account with an app password

ESP-NOW packets are limited to about 250 bytes, too small for a photo. That is why this unit also needs regular WiFi.

## Wiring

### ESP32-C3 SuperMini pins

| Side | Pins |
|---|---|
| One side | 5V, G, 3.3V, GPIO4, GPIO3, GPIO2, GPIO1, GPIO0 |
| Other side | GPIO5, GPIO6, GPIO7, GPIO8, GPIO9, GPIO10, GPIO20, GPIO21 |

### Sensor unit

| Reed switch | ESP32-C3 |
|---|---|
| Leg 1 | GPIO3 |
| Leg 2 | G |

The code assumes the switch is closed while the magnet is near, so an open door reads high. If yours works the other way round, change `DOOR_OPEN_LEVEL` in [sensor/main.py](../firmware/sensor/main.py).

GPIO3 replaces the draft's GPIO2 because GPIO2 is a strapping pin, read by the chip at boot.

### Alarm unit

| MP3 module | ESP32-C3 |
|---|---|
| VCC | 5V (some modules accept 3.3 V, so check yours) |
| GND | G |
| RX | GPIO21, through the 1 kΩ resistor |
| TX | GPIO20 |

Connect the speaker to the module's SPK+ / SPK- terminal, which may be labeled SPK_1 / SPK_2.

### Camera unit

The camera ships attached to the board, so only power is needed in normal use.

For flashing and copying files, connect the FTDI adapter:

| FTDI | ESP32-CAM |
|---|---|
| TX | U0R |
| RX | U0T |
| GND | GND |
| VCC | 5V |

To flash firmware, also connect **GPIO0 to GND** before powering on. Remove that jumper and power-cycle for normal use, including when copying the Python files.
