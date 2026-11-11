# 📡 HORTICBOTAI - IoT Smart Farm Integration Blueprint

This document contains the complete hardware specifications, circuit designs, firmware templates, and API endpoints for integrating Internet of Things (IoT) field devices with the **HORTICBOTAI** diagnostic backend.

---

## 📋 1. Hardware Options & Cost Breakdown

### 🟢 Option A: Quick MVP / Student Prototype (₹1,500 – ₹2,200 | ~$25)
* **Goal**: Test image capture + soil moisture + temperature over Wi-Fi.
* **Bill of Materials (BOM)**:
  1. `ESP32-CAM` (OV2640 2MP Camera + Flash LED) — ₹650
  2. `DHT22` (Temperature & Humidity Sensor) — ₹280
  3. `Capacitive Soil Moisture Sensor v1.2` (Corrosion-resistant) — ₹150
  4. `5V 2-Channel Relay Module` (For pump/sprayer trigger) — ₹140
  5. `FTDI USB-to-TTL Programmer` (For flashing ESP32-CAM) — ₹180
  6. `5V 2A Power Adapter / Micro-USB Breakout` — ₹250

---

### 🟡 Option B: Autonomous Solar 4G Field Camera Post (₹4,000 – ₹5,800 | ~$60)
* **Goal**: Standalone pole mounted in field; charges via solar; uploads canopy images over 4G LTE SIM.
* **Bill of Materials (BOM)**:
  1. `ESP32-S3-WROOM-1` or `ESP32-CAM` + OV5640 5MP Camera — ₹1,200
  2. `SIM7600 / A7670C 4G LTE Module` (With GPS & Antenna) — ₹1,600
  3. `10W 12V Monocrystalline Solar Panel` — ₹950
  4. `TP4056 Solar Charge Controller with Protection` — ₹120
  5. `2x 18650 Li-ion Cells (3.7V 2600mAh)` — ₹450
  6. `IP65 Weatherproof Junction Box + Glands` — ₹480

---

### 🟣 Option C: Precision 7-in-1 Soil NPK & Spore Germination Node (₹5,400 – ₹7,500 | ~$80)
* **Goal**: Detects Nitrogen, Phosphorus, Potassium, pH, Salinity (EC), and leaf dew hours to predict fungal outbreaks before visible leaf spots appear.
* **Bill of Materials (BOM)**:
  1. `RS485 Modbus 7-in-1 Soil Sensor` (N, P, K, pH, EC, Temp, Moisture) — ₹3,800
  2. `MAX485 TTL to RS485 Transceiver Module` — ₹80
  3. `Dielectric Leaf Wetness Sensor Plate` — ₹750
  4. `ESP32 DevKit V1 (30-pin)` — ₹380
  5. `Solar Battery Pack & Enclosure` — ₹1,400

---

### 🔵 Option D: Solar AI Insect Light Trap (₹2,000 – ₹3,000 | ~$30)
* **Goal**: Attracts nocturnal pests with 395nm UV LEDs, captures photos of trapped insects, and runs them through the **99.69% Pest Classifier (`pest_model.pt`)**.
* **Bill of Materials (BOM)**:
  1. `395nm UV LED Light Strip / Bulb` — ₹300
  2. `LDR Light Sensor` (Auto-activates at sunset, off at sunrise) — ₹50
  3. `ESP32-CAM` (With lens focused on trap collection base) — ₹650
  4. `Pest Inverted Funnel & Collection Box` — ₹350
  5. `Solar Charging & Battery Unit` — ₹1,100

---

## 🔌 2. Wiring & Pinout Guide (ESP32-CAM Prototype)

```
       +---------------------------------------------+
       |                 ESP32-CAM                   |
       |                                             |
       |  [5V]  <----+ 5V Power Supply (+)           |
       |  [GND] <----+ Power Supply GND (-)          |
       |                                             |
       |  [GPIO 14] <--- DHT22 Data Pin              |
       |  [GPIO 12] <--- Capacitive Soil Analog Out  |
       |  [GPIO 13] ---> Relay IN1 (Spray Pump)      |
       |  [GPIO 15] ---> Relay IN2 (Drip Valve)      |
       +---------------------------------------------+
```

---

## 💻 3. ESP32-CAM Arduino C++ Firmware (Camera Upload to HORTICBOTAI)

Save this sketch in Arduino IDE (select board: **AI Thinker ESP32-CAM**):

```cpp
#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>

// Wi-Fi Credentials
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// HORTICBOTAI Server Endpoint (Replace with your PC's local IP or domain)
const char* serverUrl = "http://192.168.1.100:8000/api/analyze";

// ESP32-CAM Pin Configuration (AI-THINKER Model)
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

void initCamera() {
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
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_VGA; // 640x480 for fast transmission
  config.jpeg_quality = 10;
  config.fb_count = 1;
  
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }
}

void captureAndSend() {
  camera_fb_t * fb = esp_camera_fb_get();
  if(!fb) {
    Serial.println("Camera capture failed");
    return;
  }
  
  if(WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverUrl);
    
    // Multipart form-data boundary
    String boundary = "----ESP32Boundary7MA4YWxkTrZu0gW";
    http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);
    
    String head = "--" + boundary + "\r\nContent-Disposition: form-data; name=\"file\"; filename=\"leaf.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n";
    String tail = "\r\n--" + boundary + "--\r\n";
    
    size_t totalLen = head.length() + fb->len + tail.length();
    uint8_t *buffer = (uint8_t*)malloc(totalLen);
    
    memcpy(buffer, head.c_str(), head.length());
    memcpy(buffer + head.length(), fb->buf, fb->len);
    memcpy(buffer + head.length() + fb->len, tail.c_str(), tail.length());
    
    int httpResponseCode = http.POST(buffer, totalLen);
    free(buffer);
    
    if (httpResponseCode > 0) {
      String response = http.getString();
      Serial.printf("Server Response (%d): %s\n", httpResponseCode, response.c_str());
    } else {
      Serial.printf("Error on sending POST: %d\n", httpResponseCode);
    }
    http.end();
  }
  
  esp_camera_fb_return(fb);
}

void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected! Initializing Camera...");
  initCamera();
}

void loop() {
  // Capture photo every 30 minutes (or test with 10 seconds)
  captureAndSend();
  delay(30 * 60 * 1000); 
}
```

---

## 🌐 4. Backend REST API Endpoints for IoT Telemetry

The following endpoints can receive telemetry from your hardware nodes:

### 1. `POST /api/analyze`
* **Input**: Multipart file `file` (JPEG image from ESP32-CAM) + optional `crop` parameter.
* **Output**: Instant diagnosis JSON including disease class, pest class, confidence, severity, NDRE/CRI score, and chemical/organic prescription.

### 2. `POST /api/iot/telemetry` (Sensor Ingestion)
```json
{
  "device_id": "NODE_PLOT_01",
  "temperature": 28.4,
  "humidity": 87.2,
  "soil_moisture": 42.5,
  "soil_ph": 6.4,
  "nitrogen_ppm": 120,
  "phosphorus_ppm": 45,
  "potassium_ppm": 180,
  "leaf_wetness_hours": 4.5
}
```

---

## 🚀 5. How to Get Started When Ready to Build

1. **Order the components** from Robu.in, Amazon, or local electronics store (Option A for prototype testing).
2. **Flash the ESP32 code** using Arduino IDE.
3. **Run your backend**: `python server.py` (or `start.bat`).
4. **Point the ESP32** to your laptop's local IP address (e.g. `http://192.168.x.x:8000/api/analyze`).
5. Watch live photos from your field camera being automatically diagnosed in real time!
