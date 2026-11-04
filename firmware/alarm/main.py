"""Alarm unit: plays a sound on the MP3 module while the door is open."""

import time

from machine import UART, Pin

import config
import door_link
from dfplayer import DFPlayer

MP3_RX_PIN = 20
MP3_TX_PIN = 21
MP3_BAUD = 9600
MP3_STARTUP_MS = 1500  # the module ignores commands until it has read the card
VOLUME = 25  # 0 to 30
ALARM_TRACK = 1

MAC_PRINT_INTERVAL_MS = 10000


def main():
    uart = UART(1, baudrate=MP3_BAUD, tx=Pin(MP3_TX_PIN), rx=Pin(MP3_RX_PIN))
    player = DFPlayer(uart)
    time.sleep_ms(MP3_STARTUP_MS)
    if not player.is_responding():
        print("MP3 module did not respond: check wiring and the SD card")
    player.set_volume(VOLUME)

    sta = door_link.start_station(config.ESPNOW_CHANNEL)
    mac = door_link.format_mac(sta.config("mac"))
    link = door_link.start_espnow()
    print("Alarm unit running, MAC", mac)

    while True:
        _, msg = link.recv(MAC_PRINT_INTERVAL_MS)
        if msg is None:
            # Native USB drops anything printed before the monitor attaches,
            # so keep repeating the address needed for config.py.
            print("Waiting for events, MAC", mac)
            continue

        event = door_link.decode_event(msg)
        if event == door_link.DOOR_OPENED:
            print("Door opened: playing alarm")
            player.play(ALARM_TRACK)
        elif event == door_link.DOOR_CLOSED:
            print("Door closed: stopping alarm")
            player.stop()


main()
