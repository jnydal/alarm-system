"""ESP-NOW helpers and the message format shared by all units."""

import espnow
import network

DOOR_CLOSED = 0
DOOR_OPENED = 1


def parse_mac(text):
    """Convert "AA:BB:CC:DD:EE:FF" to the bytes ESP-NOW expects."""
    return bytes(int(part, 16) for part in text.split(":"))


def format_mac(mac):
    return ":".join("{:02X}".format(byte) for byte in mac)


def start_station(channel=None):
    """Activate the WiFi station interface, optionally fixing its channel.

    A unit that joins a router afterwards moves to the router's channel, so
    the channel passed here only applies until then.
    """
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    if channel is not None:
        sta.disconnect()
        sta.config(channel=channel)
    return sta


def start_espnow():
    link = espnow.ESPNow()
    link.active(True)
    return link


def encode_event(event):
    return bytes([event])


def decode_event(msg):
    """Return the event in a received message, or None if it is malformed."""
    if msg is None or len(msg) != 1:
        return None
    return msg[0]
