"""Wrap a raw RGB565 camera frame in a 16-bit BMP file.

Used because the OV3660 sensor's built-in JPEG mode does not work with this
firmware, so the camera captures uncompressed frames instead.
"""

import struct

import micropython

FILE_HEADER_BYTES = 14
INFO_HEADER_BYTES = 40
MASK_BYTES = 12
PIXEL_OFFSET = FILE_HEADER_BYTES + INFO_HEADER_BYTES + MASK_BYTES
BI_BITFIELDS = 3
PIXELS_PER_METER = 2835  # 72 DPI


@micropython.viper
def _swap_bytes(buf):
    # The camera sends each pixel high byte first; BMP stores it low byte first.
    p = ptr8(buf)
    n = int(len(buf))
    i = 0
    while i < n:
        t = p[i]
        p[i] = p[i + 1]
        p[i + 1] = t
        i += 2


def from_rgb565(frame, width, height):
    """Return BMP file bytes for a width x height RGB565 frame."""
    row_bytes = width * 2
    if row_bytes % 4:
        raise ValueError("width must be even, as BMP rows are padded to 4 bytes")
    pixel_bytes = row_bytes * height
    if len(frame) != pixel_bytes:
        raise ValueError("frame is {} bytes, expected {}".format(len(frame), pixel_bytes))

    out = bytearray(PIXEL_OFFSET + pixel_bytes)
    struct.pack_into("<2sIHHI", out, 0, b"BM", len(out), 0, 0, PIXEL_OFFSET)
    struct.pack_into(
        "<IiiHHIIiiII",
        out,
        FILE_HEADER_BYTES,
        INFO_HEADER_BYTES,
        width,
        -height,  # negative height stores rows top to bottom, as the camera sends them
        1,  # colour planes
        16,  # bits per pixel
        BI_BITFIELDS,
        pixel_bytes,
        PIXELS_PER_METER,
        PIXELS_PER_METER,
        0,
        0,
    )
    struct.pack_into("<III", out, FILE_HEADER_BYTES + INFO_HEADER_BYTES, 0xF800, 0x07E0, 0x001F)

    pixels = memoryview(out)[PIXEL_OFFSET:]
    pixels[:] = frame
    _swap_bytes(pixels)
    return out
