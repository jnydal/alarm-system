"""Camera unit: watches the reed switch, tells the alarm unit, and emails a
snapshot each time the door opens.

Needs MicroPython firmware that includes the micropython-camera-API driver.
See docs/setup.md.

The OV3660 sensor's JPEG mode does not work with that firmware, so the unit
captures raw RGB565 frames and sends them as BMP files.

The alarm comes first: door events go to the alarm unit before any photo is
taken, and the unit keeps working as a plain door sensor if the camera or
WiFi fails.
"""

import gc
import time

import machine
from camera import Camera, FrameSize, GrabMode, PixelFormat
from machine import Pin

import bmp
import camera_secrets as secrets
import config
import door_link
import smtp_mail

# Reed switch on a 3 m cable, between this pin and GND, with an external
# 4.7-10 kOhm pull-up to 3.3 V and 100 nF to GND at the board. GPIO13 is free
# because the unit doesn't use the SD card, and it isn't a strapping pin.
# Don't use GPIO12: pulled high at boot, it stops the board from starting.
REED_PIN = 13

# Pin level when the door is open. With the pull-up and a switch that is
# closed while the magnet is near, an open door reads high. Swap to 0 if your
# switch works the other way round.
DOOR_OPEN_LEVEL = 1

DEBOUNCE_MS = 50
POLL_MS = 100

# A door event is sent to the alarm up to this many times until it is
# acknowledged.
ALARM_SEND_ATTEMPTS = 3
ALARM_RETRY_MS = 50

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

# Written to RTC memory, which survives machine.reset(), before rebooting
# after a failed camera init, so that a second failure doesn't reboot again.
CAMERA_RETRY_FLAG = b"cam-retry"


def start_camera():
    """Return the camera, or None if it can't be started."""
    rtc = machine.RTC()
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
        # does not help, so reboot once and try again.
        if rtc.memory() != CAMERA_RETRY_FLAG:
            print("Camera init failed:", err, "- rebooting")
            rtc.memory(CAMERA_RETRY_FLAG)
            time.sleep(2)
            machine.reset()
        print("Camera init failed again:", err, "- running without photos")
        rtc.memory(b"")
        return None
    rtc.memory(b"")
    cam.set_vflip(FLIP_VERTICAL)
    cam.set_hmirror(MIRROR_HORIZONTAL)
    return cam


def start_radio():
    """Start ESP-NOW towards the alarm, and begin joining WiFi.

    The connection completes in the background, so the door is watched while
    it does. Once joined, the radio follows the router's channel, which is why
    ESPNOW_CHANNEL has to match it.
    """
    sta = door_link.start_station(config.ESPNOW_CHANNEL)
    # Power saving turns the radio off periodically, which loses ESP-NOW packets.
    sta.config(pm=sta.PM_NONE)
    link = door_link.start_espnow()
    alarm = door_link.parse_mac(config.ALARM_MAC)
    link.add_peer(alarm)
    print("Camera unit running, MAC", door_link.format_mac(sta.config("mac")))
    sta.connect(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
    return sta, link, alarm


def report_wifi(sta):
    channel = sta.config("channel")
    print("WiFi connected, router channel", channel)
    if channel != config.ESPNOW_CHANNEL:
        print(
            "WARNING: config.ESPNOW_CHANNEL is {}, so the alarm will not hear "
            "door events. Set it to {} and reflash both units.".format(
                config.ESPNOW_CHANNEL, channel
            )
        )


def notify_alarm(link, alarm, event):
    for attempt in range(ALARM_SEND_ATTEMPTS):
        try:
            if link.send(alarm, door_link.encode_event(event)):
                print("Event", event, "delivered to alarm")
                return
        except OSError as err:
            print("Send error:", err)
        time.sleep_ms(ALARM_RETRY_MS)
    print("Event", event, "not acknowledged by alarm")


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


def on_door_opened(cam, sta):
    if cam is None:
        return
    if not sta.isconnected():
        print("No WiFi: skipping snapshot")
        return
    print("Capturing and emailing")
    try:
        email_snapshot(cam)
        print("Email sent")
    except Exception as err:
        # Stay running so that the door is still watched.
        print("Snapshot failed:", err)


def main():
    # Set before WiFi starts, as changing it later drops the connection.
    machine.freq(CPU_HZ)
    reed = Pin(REED_PIN, Pin.IN, Pin.PULL_UP)
    cam = start_camera()
    sta, link, alarm = start_radio()

    last_level = reed.value()
    wifi_reported = False

    while True:
        if not wifi_reported and sta.isconnected():
            report_wifi(sta)
            wifi_reported = True

        # Polling resumes after an email, so a door that closed while the email
        # was being sent is still reported then.
        if reed.value() != last_level:
            time.sleep_ms(DEBOUNCE_MS)
            level = reed.value()
            if level != last_level:
                last_level = level
                opened = level == DOOR_OPEN_LEVEL
                event = door_link.DOOR_OPENED if opened else door_link.DOOR_CLOSED
                print("Door", "opened" if opened else "closed")
                notify_alarm(link, alarm, event)
                if opened:
                    on_door_opened(cam, sta)
        time.sleep_ms(POLL_MS)


main()
