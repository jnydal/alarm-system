"""Camera unit: emails a snapshot each time the door opens.

Needs MicroPython firmware that includes the micropython-camera-API driver.
See docs/setup.md.

The OV3660 sensor's JPEG mode does not work with that firmware, so the unit
captures raw RGB565 frames and sends them as BMP files.
"""

import gc
import time

import machine
from camera import Camera, FrameSize, GrabMode, PixelFormat

import bmp
import camera_secrets as secrets
import config
import door_link
import smtp_mail

# AI-Thinker ESP32-CAM pin map, with the data pins ordered D0 to D7.
CAMERA_PINS = {
    "data_pins": [5, 18, 19, 21, 36, 39, 34, 35],
    "vsync_pin": 25,
    "href_pin": 23,
    "sda_pin": 26,
    "scl_pin": 27,
    "pclk_pin": 22,
    "xclk_pin": 0,
    "powerdown_pin": 32,
    "reset_pin": -1,
}
XCLK_HZ = 20000000
# 320 x 240. Each snapshot is width x height x 2 bytes, about 150 KB here.
FRAME_SIZE = FrameSize.QVGA
# The OV3660 sits upside down on this board, so flipping both ways turns the
# picture the right way up. Change these if the camera is mounted rotated.
FLIP_VERTICAL = True
MIRROR_HORIZONTAL = True
# The TLS handshake with the mail server sometimes fails on this board, so
# each snapshot is sent up to this many times.
SEND_ATTEMPTS = 3
RETRY_DELAY_S = 2
CPU_HZ = 240000000  # speeds up the TLS handshake


def connect_wifi():
    sta = door_link.start_station()
    # Power saving turns the radio off periodically, which loses ESP-NOW packets.
    sta.config(pm=sta.PM_NONE)
    sta.connect(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
    while not sta.isconnected():
        print(".", end="")
        time.sleep_ms(500)
    print("\nWiFi connected")
    return sta


def report_radio(sta):
    channel = sta.config("channel")
    print("Camera unit running, MAC", door_link.format_mac(sta.config("mac")))
    print("Router channel", channel)
    if channel != config.ESPNOW_CHANNEL:
        print(
            "WARNING: config.ESPNOW_CHANNEL is {}, so door events will not arrive. "
            "Set it to {} and reflash all units.".format(config.ESPNOW_CHANNEL, channel)
        )


def capture_snapshot(cam):
    # In this grab mode the buffered frame was taken when the last one was
    # released, possibly hours ago. Throw it away to get a current picture.
    cam.capture()
    cam.free_buffer()
    image = bmp.from_rgb565(cam.capture(), cam.get_pixel_width(), cam.get_pixel_height())
    cam.free_buffer()
    return image


def email_snapshot(cam):
    image = capture_snapshot(cam)
    # Free the heap before TLS allocates its buffers.
    gc.collect()
    for attempt in range(1, SEND_ATTEMPTS + 1):
        try:
            smtp_mail.send_image(
                secrets.SMTP_HOST,
                secrets.SMTP_PORT,
                secrets.SENDER_EMAIL,
                secrets.SENDER_PASSWORD,
                secrets.RECIPIENT_EMAIL,
                "Door opened - snapshot attached",
                "The door was opened. See the attached photo.",
                image,
                "snapshot.bmp",
                "image/bmp",
            )
            return
        except OSError as err:
            if attempt == SEND_ATTEMPTS:
                raise
            print("Send attempt {} failed: {}, retrying".format(attempt, err))
            gc.collect()
            time.sleep(RETRY_DELAY_S)


def start_camera():
    try:
        cam = Camera(
            pixel_format=PixelFormat.RGB565,
            frame_size=FRAME_SIZE,
            fb_count=1,
            grab_mode=GrabMode.WHEN_EMPTY,
            xclk_freq=XCLK_HZ,
            **CAMERA_PINS
        )
    except OSError as err:
        # Camera init occasionally fails at boot, and retrying in the same boot
        # does not help, so reboot and try again.
        print("Camera init failed:", err, "- rebooting")
        time.sleep(2)
        machine.reset()
    cam.set_vflip(FLIP_VERTICAL)
    cam.set_hmirror(MIRROR_HORIZONTAL)
    return cam


def main():
    # Set before WiFi starts, as changing it later drops the connection.
    machine.freq(CPU_HZ)
    cam = start_camera()
    sta = connect_wifi()
    link = door_link.start_espnow()
    report_radio(sta)

    while True:
        _, msg = link.recv()
        if door_link.decode_event(msg) != door_link.DOOR_OPENED:
            continue
        print("Door opened: capturing and emailing")
        try:
            email_snapshot(cam)
            print("Email sent")
        except Exception as err:
            # Stay running so that the next door event still gets a try.
            print("Snapshot failed:", err)


main()
