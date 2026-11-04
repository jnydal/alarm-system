"""Camera unit: emails a snapshot each time the door opens.

Needs MicroPython firmware that includes the micropython-camera-API driver.
See docs/setup.md.
"""

import time

from camera import Camera, FrameSize, GrabMode, PixelFormat

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
JPEG_QUALITY = 85  # 0 to 100, higher is better


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
    jpeg = bytes(cam.capture())
    cam.free_buffer()
    return jpeg


def email_snapshot(cam):
    jpeg = capture_snapshot(cam)
    smtp_mail.send_jpeg(
        secrets.SMTP_HOST,
        secrets.SMTP_PORT,
        secrets.SENDER_EMAIL,
        secrets.SENDER_PASSWORD,
        secrets.RECIPIENT_EMAIL,
        "Door opened - snapshot attached",
        "The door was opened. See the attached photo.",
        jpeg,
        "snapshot.jpg",
    )


def main():
    cam = Camera(
        pixel_format=PixelFormat.JPEG,
        frame_size=FrameSize.VGA,
        jpeg_quality=JPEG_QUALITY,
        fb_count=1,
        grab_mode=GrabMode.WHEN_EMPTY,
        xclk_freq=XCLK_HZ,
        **CAMERA_PINS
    )
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
