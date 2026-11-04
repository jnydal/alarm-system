"""Sensor unit: reports reed switch changes to the alarm and camera units."""

import time

from machine import Pin

import config
import door_link

REED_PIN = 3

# Pin level when the door is open. With the pull-up below and a switch that is
# closed while the magnet is near, an open door reads high. Swap to 0 if your
# switch works the other way round.
DOOR_OPEN_LEVEL = 1

DEBOUNCE_MS = 50
POLL_MS = 100


def send_event(link, peers, event):
    for peer in peers:
        try:
            delivered = link.send(peer, door_link.encode_event(event))
        except OSError as err:
            print("Send error to", door_link.format_mac(peer), err)
            continue
        status = "delivered" if delivered else "not acknowledged"
        print("Event", event, status, "by", door_link.format_mac(peer))


def main():
    reed = Pin(REED_PIN, Pin.IN, Pin.PULL_UP)

    door_link.start_station(config.ESPNOW_CHANNEL)
    link = door_link.start_espnow()

    peers = [door_link.parse_mac(config.ALARM_MAC)]
    if config.CAMERA_ENABLED:
        peers.append(door_link.parse_mac(config.CAMERA_MAC))
    for peer in peers:
        link.add_peer(peer)

    last_level = reed.value()
    print("Sensor unit running")

    while True:
        if reed.value() != last_level:
            time.sleep_ms(DEBOUNCE_MS)
            level = reed.value()
            if level != last_level:
                last_level = level
                opened = level == DOOR_OPEN_LEVEL
                event = door_link.DOOR_OPENED if opened else door_link.DOOR_CLOSED
                send_event(link, peers, event)
        time.sleep_ms(POLL_MS)


main()
