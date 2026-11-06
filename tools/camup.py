"""Copy files to the camera board and watch its output, in place of mpremote.

The ESP32-CAM's USB adapter holds the chip in reset while DTR/RTS are
asserted, which mpremote does when it opens the port. This script keeps those
lines released and speaks MicroPython's raw REPL protocol directly.

Usage:
    py tools/camup.py PORT [FILE ...] [--exec CODE] [--reset] [--monitor]

    FILE       copy a local file to the board's root, under the same name
    --exec     run a line of Python on the board and print its output
    --reset    restart the board when done, so main.py runs
    --monitor  restart the board and print its output until Ctrl+C

Example:
    py tools/camup.py COM9 firmware/config.py --reset
"""

import binascii
import os
import sys
import time

import serial

BAUD = 115200
RAW_PROMPT = b"raw REPL; CTRL-B to exit\r\n>"
CHUNK_BYTES = 256
EXEC_TIMEOUT_S = 180


class Board:
    def __init__(self, port):
        self.serial = serial.Serial()
        self.serial.port = port
        self.serial.baudrate = BAUD
        self.serial.timeout = 0.2
        self.serial.dtr = False
        self.serial.rts = False
        self.serial.open()
        self.buffer = b""

    def close(self):
        self.serial.close()

    def reset(self):
        # RTS drives the chip's EN pin through the adapter.
        self.serial.rts = True
        time.sleep(0.1)
        self.serial.rts = False

    def read_until(self, marker, timeout=10):
        end = time.time() + timeout
        while marker not in self.buffer:
            if time.time() > end:
                raise RuntimeError("timed out waiting for {!r}, got {!r}".format(marker, self.buffer[-200:]))
            self.buffer += self.serial.read(256)
        i = self.buffer.index(marker) + len(marker)
        out, self.buffer = self.buffer[:i], self.buffer[i:]
        return out

    def enter_raw_repl(self):
        time.sleep(1.5)  # opening the port may reboot the board
        # Hard reset, then interrupt during boot so main.py never claims the
        # camera: a soft reset does not release the camera driver.
        self.reset()
        end = time.time() + 2.0
        while time.time() < end:
            self.serial.write(b"\x03")
            time.sleep(0.03)
        self.serial.write(b"\r\x03\x03")
        time.sleep(0.3)
        self.serial.reset_input_buffer()
        self.buffer = b""
        self.serial.write(b"\r\x01")
        self.read_until(RAW_PROMPT)
        self.serial.write(b"\x04")
        self.read_until(b"soft reboot")
        self.read_until(RAW_PROMPT)

    def leave_raw_repl(self):
        self.serial.write(b"\x02")

    def run(self, code, timeout=EXEC_TIMEOUT_S):
        self.serial.write(code.encode() + b"\x04")
        self.read_until(b"OK")
        out = self.read_until(b"\x04", timeout)[:-1].decode(errors="replace")
        err = self.read_until(b"\x04>", timeout)[:-2].decode(errors="replace")
        if err.strip():
            raise RuntimeError(out + err)
        return out

    def put(self, path):
        name = os.path.basename(path)
        with open(path, "rb") as f:
            data = f.read()
        self.run("import binascii\nf=open({!r},'wb')".format(name))
        for i in range(0, len(data), CHUNK_BYTES):
            chunk = binascii.b2a_base64(data[i : i + CHUNK_BYTES], newline=False).decode()
            self.run("f.write(binascii.a2b_base64({!r}))".format(chunk))
        self.run("f.close()")
        print("copied", name, len(data), "bytes", file=sys.stderr)

    def monitor(self):
        self.reset()
        try:
            while True:
                data = self.serial.read(512)
                if data:
                    sys.stdout.write(data.decode(errors="replace"))
                    sys.stdout.flush()
        except KeyboardInterrupt:
            pass


def main(args):
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return
    board = Board(args.pop(0))
    try:
        files, code, reset, monitor = [], [], False, False
        while args:
            arg = args.pop(0)
            if arg == "--exec":
                code.append(args.pop(0))
            elif arg == "--reset":
                reset = True
            elif arg == "--monitor":
                monitor = True
            else:
                files.append(arg)
        if files or code:
            board.enter_raw_repl()
            for path in files:
                board.put(path)
            for line in code:
                print(board.run(line), end="")
            board.leave_raw_repl()
        if monitor:
            board.monitor()
        elif reset:
            board.reset()
    finally:
        board.close()


if __name__ == "__main__":
    main(sys.argv[1:])
