# DIY Door Alarm — 2x ESP32-C3 \+ Generic UART MP3 Module (+ optional camera unit)

A wireless door alarm: a battery-friendly sensor unit on the door, and a separate alarm unit that plays an MP3 sound through a speaker. The two boards talk directly to each other over **ESP-NOW** — no WiFi router or internet connection required. An optional third unit adds a camera snapshot whenever the door opens.

**Board note:** both the sensor and alarm units use the same chip — ESP32-C3 — just on two separate boards. Confirmed for this build: **ESP32-C3 SuperMini** boards (16-pin, USB-C, native-USB, no separate USB-serial chip). The original two-chip design (C3 \+ C2) was just a cost choice by whoever wrote the first version of this doc; using ESP32-C3 for both units works identically in code, since ESP-NOW and Arduino core support are the same across both boards.

## How it works

```
                              +---ESP-NOW---> [ESP32-C3 "Alarm"] --UART--> [UART MP3 module] --> [Speaker]
[Door] --reed switch--> [ESP32-C3 "Sensor"] --+
                              +---ESP-NOW---> [ESP32-CAM "Camera"] --WiFi/SMTP--> [Your email inbox]
```

ESP-NOW uses the WiFi radio hardware but skips routers, IP addresses, and connection handshakes — the sensor board sends small packets directly to each other device's MAC address. This means:

- No home WiFi/router dependency for the door-detection trigger itself  
- Very low latency (near-instant trigger)  
- Works even if your internet is down

**Why a separate camera unit:** the ESP32-C3 has no camera interface (no DVP/LCD\_CAM peripheral), so it physically cannot drive a camera module. The camera function lives on its own ESP32-CAM (or ESP32-S3-CAM) board instead, triggered by the same ESP-NOW signal from the door sensor. This keeps the original two-unit alarm system untouched — you're adding a third node, not modifying the first two.

---

## Parts list

### Sensor unit (on the door)

- ESP32-C3 dev board (e.g. Seeed XIAO ESP32C3, or generic)  
- Magnetic reed switch (door/window alarm sensor)  
- 10kΩ resistor (only needed if not using internal pull-up)  
- USB power, or LiPo battery \+ charging board for wireless operation

### Alarm unit (plays the sound)

- ESP32-C3 dev board (e.g. Seeed XIAO ESP32C3, or a generic ESP32-C3 SuperMini board)  
- Generic UART serial MP3 player module with onboard mono amplifier \+ speaker terminal (DFPlayer Mini-compatible protocol — verify against the seller's spec before relying on the code below; if it isn't compatible, the `DFRobotDFPlayerMini` library commands may need adjusting)  
- microSD card (FAT32 formatted)  
- Small speaker (3W/4Ω or 8Ω — check the module's amp rating; many of these boards are rated similarly to the DFPlayer Mini at \~3W into 4Ω)  
- 1kΩ resistor (in series on the module's RX line, protects it if powered at 5V from a 3.3V signal)

### Camera unit (optional — snapshot on door open, emailed to you)

- ESP32-CAM board (AI-Thinker with OV2640, or ESP32-S3-CAM) — needs the DVP/LCD\_CAM interface the C3 lacks  
- USB-to-serial (FTDI) adapter for flashing, since most ESP32-CAM boards have no onboard USB  
- 5V power supply (USB power bank or wall adapter — camera \+ WiFi draws more current than the other two units)  
- microSD card (optional, if you want to also save snapshots locally on the camera board)  
- Home WiFi network (this unit uses regular WiFi, not ESP-NOW, since ESP-NOW packets are too small (\~250 bytes) for an image)  
- An email account to send from, with an **app password** generated for it (Gmail, Outlook, etc. — regular account passwords won't work for SMTP logins from a device like this)  
- `ESP Mail Client` library (by Mobizt) for sending the email directly from the board

---

## Wiring

### Reed switch → ESP32-C3

- One leg → GPIO2  
- Other leg → GND  
- Use `INPUT_PULLUP` in code (circuit closed \= door closed, open \= door open, or vice versa depending on your switch)

**Note:** GPIO2 is a strapping pin on ESP32-C3 (it's read during boot to help select flash voltage mode). This is a very common pin choice for a reed switch and normally works fine, but if the board happens to power on while the door is open (pulling GPIO2 low), you could occasionally see a boot hiccup. If you ever notice erratic boot behavior on the sensor unit, try power-cycling it with the door closed, or move the reed switch to a non-strapping pin (e.g. GPIO3 or GPIO4) instead.

### UART MP3 module → ESP32-C3 (Alarm unit)

- Module VCC → 5V (check your specific module's requirement; some accept 3.3V)  
- Module GND → GND  
- Module RX ← ESP32-C3 **GPIO21** (through 1kΩ resistor if the module is powered at 5V)  
- Module TX → ESP32-C3 **GPIO20**  
- Speaker → SPK+ / SPK- (or SPK\_1 / SPK\_2) terminal on the module

**Confirmed pinout (ESP32-C3 SuperMini):** based on the actual board, pins are labeled 5V / G / 3.3V / GPIO4 / GPIO3 / GPIO2 / GPIO1 / GPIO0 down one side, and GPIO5 / GPIO6 / GPIO7 / GPIO8 / GPIO9 / GPIO10 / GPIO20 / GPIO21 down the other. GPIO20/21 are the chip's actual hardware UART0 pins (RX/TX) — they're free to use here because this board connects USB-C straight to the chip's native USB for the Serial Monitor, rather than routing through UART0 via a separate USB-serial chip. That makes them a solid, low-risk choice for talking to the MP3 module over hardware `Serial1`.

### ESP32-CAM (optional camera unit)

- No extra wiring beyond power — the OV2640 camera ships pre-attached to the board's camera connector on most ESP32-CAM boards  
- FTDI adapter (for flashing only): FTDI TX → board U0R, FTDI RX → board U0T, FTDI GND → GND, FTDI VCC → 5V  
- **GPIO0 must be tied to GND during flashing** (jumper wire), then removed/floating for normal boot  
- Power the board from a proper 5V supply — brownouts during WiFi transmission are the most common cause of ESP32-CAM flakiness

---

## Code — Sensor unit (ESP32-C3)

```c
#include <esp_now.h>
#include <WiFi.h>

#define REED_PIN 2

// Replace with the MAC address of your alarm unit's ESP32-C3
uint8_t alarmMac[] = {0xXX, 0xXX, 0xXX, 0xXX, 0xXX, 0xXX};

// Replace with the MAC address of your ESP32-CAM camera unit (optional)
uint8_t cameraMac[] = {0xYY, 0xYY, 0xYY, 0xYY, 0xYY, 0xYY};

typedef struct {
  uint8_t event; // 1 = door opened, 0 = door closed
} Message;

Message msg;
bool lastState = HIGH;

void onSent(const uint8_t *mac, esp_now_send_status_t status) {
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Sent OK" : "Send failed");
}

void setup() {
  Serial.begin(115200);
  pinMode(REED_PIN, INPUT_PULLUP);

  WiFi.mode(WIFI_STA);
  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW init failed");
    return;
  }
  esp_now_register_send_cb(onSent);

  esp_now_peer_info_t peerInfo = {};
  peerInfo.channel = 0;
  peerInfo.encrypt = false;

  memcpy(peerInfo.peer_addr, alarmMac, 6);
  esp_now_add_peer(&peerInfo);

  // Remove this block if you're not using the camera unit
  memcpy(peerInfo.peer_addr, cameraMac, 6);
  esp_now_add_peer(&peerInfo);
}

void loop() {
  bool state = digitalRead(REED_PIN);
  if (state != lastState) {
    delay(50); // debounce
    state = digitalRead(REED_PIN);
    if (state != lastState) {
      msg.event = (state == HIGH) ? 1 : 0; // HIGH = open, depends on your wiring
      esp_now_send(alarmMac, (uint8_t*)&msg, sizeof(msg));
      esp_now_send(cameraMac, (uint8_t*)&msg, sizeof(msg)); // remove if not using camera unit
      lastState = state;
    }
  }
  delay(100);
}
```

---

## Code — Alarm unit (ESP32-C3)

```c
#include <esp_now.h>
#include <WiFi.h>
#include <DFRobotDFPlayerMini.h> // works if your generic UART MP3 module uses a DFPlayer-compatible command set — verify against the module's datasheet first

// Using hardware Serial1 instead of SoftwareSerial, since SoftwareSerial
// isn't reliable on RISC-V-based ESP32-C3 chips.
// GPIO20 = RX, GPIO21 = TX — these are the ESP32-C3 SuperMini's hardware
// UART0 pins, free to use here since this board's Serial Monitor runs over
// native USB rather than through UART0.
#define MP3_RX_PIN 20
#define MP3_TX_PIN 21

DFRobotDFPlayerMini player;

typedef struct {
  uint8_t event;
} Message;

void onReceive(const uint8_t *mac, const uint8_t *data, int len) {
  Message msg;
  memcpy(&msg, data, sizeof(msg));
  if (msg.event == 1) {
    Serial.println("Door opened -> playing alarm");
    player.play(1); // plays 0001.mp3
  } else {
    player.stop(); // optional: stop when door closes
  }
}

void setup() {
  Serial.begin(115200);
  Serial1.begin(9600, SERIAL_8N1, MP3_RX_PIN, MP3_TX_PIN);

  if (!player.begin(Serial1)) {
    Serial.println("MP3 module init failed");
  }
  player.volume(25); // 0–30

  WiFi.mode(WIFI_STA);
  Serial.println(WiFi.macAddress()); // note this down for the sensor unit!

  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW init failed");
    return;
  }
  esp_now_register_recv_cb(onReceive);
}

void loop() {
  // nothing needed here, all event-driven
}
```

---

## Code — Camera unit (ESP32-CAM, optional)

This uses regular WiFi (to log into your email provider's SMTP server) plus ESP-NOW (to receive the instant trigger from the door sensor) side by side — the ESP32 can do both at once in station mode.

Install the **ESP Mail Client** library (by Mobizt) via Library Manager before compiling.

```c
#include <esp_now.h>
#include <WiFi.h>
#include <esp_camera.h>
#include <ESP_Mail_Client.h>

// AI-Thinker ESP32-CAM pin map
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

const char* ssid     = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// SMTP settings — Gmail example (use an App Password, not your normal password)
#define SMTP_HOST "smtp.gmail.com"
#define SMTP_PORT 465
#define AUTHOR_EMAIL "your.account@gmail.com"
#define AUTHOR_PASSWORD "your16charAppPassword"
#define RECIPIENT_EMAIL "your.account@gmail.com" // can be the same address, or a different one

SMTPSession smtp;

typedef struct {
  uint8_t event;
} Message;

void onReceive(const uint8_t *mac, const uint8_t *data, int len) {
  Message msg;
  memcpy(&msg, data, sizeof(msg));
  if (msg.event == 1) {
    Serial.println("Door opened -> capturing photo and emailing");
    capturePhotoAndEmail();
  }
}

void capturePhotoAndEmail() {
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Camera capture failed");
    return;
  }

  Session_Config session;
  session.server.host_name = SMTP_HOST;
  session.server.port = SMTP_PORT;
  session.login.email = AUTHOR_EMAIL;
  session.login.password = AUTHOR_PASSWORD;
  session.login.user_domain = "";

  SMTP_Message message;
  message.sender.name = "Door Alarm";
  message.sender.email = AUTHOR_EMAIL;
  message.subject = "Door opened - snapshot attached";
  message.addRecipient("Me", RECIPIENT_EMAIL);
  message.text.content = "Motion detected at the front door. See attached photo.";

  SMTP_Attachment att;
  att.descr.filename = "snapshot.jpg";
  att.descr.mime = "image/jpeg";
  att.blob.data = fb->buf;
  att.blob.size = fb->len;
  att.type = esp_mail_attach_type_data;
  message.addAttachment(att);

  smtp.connect(&session);
  if (!MailClient.sendMail(&smtp, &message)) {
    Serial.println("Email send failed: " + smtp.errorReason());
  } else {
    Serial.println("Email sent");
  }
  smtp.closeSession();

  esp_camera_fb_return(fb);
}

void setupCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_VGA; // 640x480 — bump up if you want higher res
  config.jpeg_quality = 12;
  config.fb_count = 1;

  if (esp_camera_init(&config) != ESP_OK) {
    Serial.println("Camera init failed");
  }
}

void setup() {
  Serial.begin(115200);
  setupCamera();

  // Connect to home WiFi (needed to reach the SMTP server)
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
  Serial.println(WiFi.macAddress()); // note this down for the sensor unit!

  // ESP-NOW works alongside the WiFi connection above
  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW init failed");
    return;
  }
  esp_now_register_recv_cb(onReceive);
}

void loop() {
  // nothing needed here, all event-driven
}
```

---

## Build steps

1. **Get the alarm unit's ESP32-C3 MAC address.** Flash the alarm-unit code first (peer MAC doesn't matter yet), open Serial Monitor, and note the printed `WiFi.macAddress()`. You'll need this for the sensor unit.

2. **Flash both boards.** Update `alarmMac[]` in the sensor code with the real MAC address, then flash the sensor code to the sensor's ESP32-C3 and the alarm code to the alarm unit's ESP32-C3 (Arduino IDE or PlatformIO). Install the `DFRobotDFPlayerMini` library via Library Manager (used here to talk to the generic UART MP3 module, assuming a compatible command set).

3. **Prepare the SD card.** Format as FAT32. Copy your alarm sound in as `0001.mp3` (root folder, or `/mp3` folder depending on your DFPlayer library version). Insert before powering the module on.

4. **Wire and test on the bench.** Connect the reed switch to the sensor's ESP32-C3, and the UART MP3 module \+ speaker to the alarm unit's ESP32-C3. Power both boards via USB, open two Serial Monitor windows, and trigger the reed switch by hand to confirm the alarm plays.

5. **Mount at the door.** Attach the reed switch and magnet to the door frame and door leaf (a few mm gap works best). Mount the ESP32-C3 nearby — ideally on a LiPo battery so it isn't tethered to an outlet.

6. **Place the alarm unit.** Put the alarm unit's ESP32-C3 \+ UART MP3 module \+ speaker wherever you want the sound — hallway, bedroom, etc. ESP-NOW range is similar to normal WiFi range (same radio hardware), typically 30–50m indoors through a wall or two.

### Optional: adding the camera unit

7. **Generate an app password.** In your email account's security settings, create an app-specific password (with Gmail: Google Account → Security → 2-Step Verification → App Passwords). Regular account passwords are blocked for SMTP logins from devices like this, so this step is required, not optional.

8. **Get the ESP32-CAM's MAC address.** Flash the camera code (with WiFi credentials, SMTP settings, and app password filled in) using the FTDI adapter, with GPIO0 grounded during flashing. Open Serial Monitor and note the printed MAC address once it connects to WiFi.

9. **Update and reflash the sensor unit.** Add the camera unit's MAC address to `cameraMac[]` in the sensor code and reflash the ESP32-C3.

10. **Test end-to-end.** Trigger the reed switch and confirm: the alarm plays on the alarm unit's ESP32-C3 *and* an email with the photo attached arrives in your inbox within a few seconds.

11. **Mount the camera unit** with a view of the door — a small enclosure with a lens cutout works well. Make sure it's on stable 5V power; ESP32-CAM boards are notably power-hungry during a WiFi transmission and will brown-out on a weak supply.

---

## Notes & troubleshooting

- **Debounce:** reed switches can chatter on state change. The 50ms delay in the code should suffice, but increase it if you see double-triggers.  
- **ESP32-C3 UART (alarm unit):** the code above already uses hardware `Serial1` rather than `SoftwareSerial`, since `SoftwareSerial` isn't reliable on RISC-V-based ESP32-C3 chips. If the alarm doesn't respond, double-check the RX/TX GPIO numbers match your specific board's actual free pins (they vary between SuperMini, XIAO, and generic ESP32-C3 dev boards).  
- **Generic MP3 module compatibility:** if `player.begin()` fails or commands don't do anything, your module's command protocol may not exactly match the DFPlayer Mini's. Check the seller's listing/manual for the exact chipset (many clones use a DFPlayer-compatible set, but not all) before assuming the code will work unmodified.  
- **Range:** if the signal doesn't reach reliably, move the alarm unit closer or consider an ESP-NOW repeater node.  
- **Power:** for long-term battery operation on the sensor unit, add deep-sleep with wake-on-GPIO-interrupt so it isn't always fully awake.  
- **Camera brownouts:** ESP32-CAM boards are known to reset or fail capture under a weak/USB-hub power supply — use a proper 5V/2A supply if you see random reboots.  
- **Camera \+ ESP-NOW coexistence:** the ESP32-CAM runs regular WiFi (to reach the SMTP server) and ESP-NOW at the same time on the same radio; this works fine in station mode but means the camera unit must stay associated with your home WiFi network to receive the trigger reliably.  
- **Why not put the camera on the alarm unit's ESP32-C3 instead:** same limitation as the sensor unit's ESP32-C3 — no DVP/LCD\_CAM interface — so it can't drive a camera either. The camera genuinely needs its own ESP32-CAM/S3-CAM board.  
- **Email credentials in firmware:** the app password and email login live in the camera unit's compiled firmware. This is fine for a home project, but note that anyone with physical access to the board and a way to dump its flash could read them out — don't reuse a sensitive password here.  
- **SMTP rate limits / spam filters:** most providers are fine with occasional emails but may flag frequent automated sends. If break-ins somehow trigger repeatedly in a short window, consider adding a simple cooldown (e.g. skip sending again within 60 seconds of the last email) to avoid your account getting flagged or your inbox getting flooded.  
- **Gmail-specific:** if `smtp.gmail.com` on port 465 doesn't connect, double check 2-Step Verification is enabled on the account (required before App Passwords can be created) and that you copied the 16-character app password without spaces.

## Possible extensions

- Multiple sensor units (one per door/window) reporting to a single alarm unit  
- A "silence/disarm" push button on the alarm unit  
- Bridging to real WiFi \+ MQTT/HTTP instead of ESP-NOW, for phone notifications or remote control over the internet  
- Local snapshot storage on the camera unit's microSD card as a backup to the email  
- Short video clip instead of a single still, if your email provider's attachment size limit allows it (ESP32-CAM can do short MJPEG bursts)  
- A cooldown timer so repeated triggers don't send an email every single time within a short window