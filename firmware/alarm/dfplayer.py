"""Minimal driver for DFPlayer Mini-compatible UART MP3 modules.

Every command is a fixed 10-byte frame:
    7E FF 06 <command> <ack> <param high> <param low> <checksum high> <checksum low> EF
"""

import time

CMD_PLAY_TRACK = 0x03
CMD_SET_VOLUME = 0x06
CMD_STOP = 0x16
CMD_QUERY_VOLUME = 0x43


def build_frame(command, param=0):
    body = bytes([0xFF, 0x06, command, 0x00, (param >> 8) & 0xFF, param & 0xFF])
    checksum = -sum(body) & 0xFFFF
    return b"\x7e" + body + bytes([checksum >> 8, checksum & 0xFF, 0xEF])


class DFPlayer:
    def __init__(self, uart):
        self._uart = uart

    def _send(self, command, param=0):
        self._uart.write(build_frame(command, param))

    def play(self, track=1):
        """Play a track. The number is the file's position on the card, not its name."""
        self._send(CMD_PLAY_TRACK, track)

    def stop(self):
        self._send(CMD_STOP)

    def set_volume(self, volume):
        """Set the volume, from 0 to 30."""
        self._send(CMD_SET_VOLUME, volume)

    def is_responding(self, timeout_ms=500):
        """Ask for the volume and report whether the module sent anything back."""
        self._uart.read()  # discard anything already buffered
        self._send(CMD_QUERY_VOLUME)
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            if self._uart.any():
                return True
            time.sleep_ms(10)
        return False
