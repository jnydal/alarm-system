"""Send one email with an image attachment over SMTP on an implicit-TLS port."""

import binascii
import socket
import ssl

BOUNDARY = "door-alarm-boundary"
BASE64_LINE_BYTES = 57  # encodes to the 76-character line length MIME requires
WRITE_BUFFER_BYTES = 2048
SOCKET_TIMEOUT_S = 30


def _b64(data):
    return binascii.b2a_base64(data)[:-1]  # drop the trailing newline


def _expect(sock, code):
    # Multi-line replies use "250-text" on every line but the last ("250 text").
    while True:
        line = sock.readline()
        if not line:
            raise OSError("SMTP connection closed")
        if line[3:4] != b"-":
            break
    if int(line[:3]) != code:
        raise OSError("SMTP error, expected {}: {}".format(code, line))


def _command(sock, text, code):
    sock.write(text + b"\r\n")
    _expect(sock, code)


def _write_base64(sock, data):
    view = memoryview(data)
    pending = bytearray()
    for start in range(0, len(view), BASE64_LINE_BYTES):
        pending += _b64(view[start : start + BASE64_LINE_BYTES]) + b"\r\n"
        if len(pending) >= WRITE_BUFFER_BYTES:
            sock.write(pending)
            pending = bytearray()
    if pending:
        sock.write(pending)


def _headers(sender, recipient, subject, body, filename, content_type):
    lines = (
        "From: Door Alarm <{}>".format(sender),
        "To: {}".format(recipient),
        "Subject: {}".format(subject),
        "MIME-Version: 1.0",
        'Content-Type: multipart/mixed; boundary="{}"'.format(BOUNDARY),
        "",
        "--{}".format(BOUNDARY),
        'Content-Type: text/plain; charset="utf-8"',
        "",
        body,
        "",
        "--{}".format(BOUNDARY),
        'Content-Type: {}; name="{}"'.format(content_type, filename),
        'Content-Disposition: attachment; filename="{}"'.format(filename),
        "Content-Transfer-Encoding: base64",
        "",
        "",
    )
    return "\r\n".join(lines).encode()


def send_image(
    host, port, sender, password, recipient, subject, body, image, filename, content_type
):
    """Send the email. Raises OSError if the server refuses or the link fails."""
    address = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)[0][-1]
    raw = socket.socket()
    try:
        raw.settimeout(SOCKET_TIMEOUT_S)
        raw.connect(address)
        sock = ssl.wrap_socket(raw, server_hostname=host)

        _expect(sock, 220)
        _command(sock, b"EHLO door-alarm", 250)
        _command(sock, b"AUTH LOGIN", 334)
        _command(sock, _b64(sender.encode()), 334)
        _command(sock, _b64(password.encode()), 235)
        _command(sock, "MAIL FROM:<{}>".format(sender).encode(), 250)
        _command(sock, "RCPT TO:<{}>".format(recipient).encode(), 250)
        _command(sock, b"DATA", 354)

        sock.write(_headers(sender, recipient, subject, body, filename, content_type))
        _write_base64(sock, image)
        sock.write("\r\n--{}--\r\n".format(BOUNDARY).encode())
        _command(sock, b".", 250)

        sock.write(b"QUIT\r\n")
    finally:
        raw.close()
