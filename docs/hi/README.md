<div align="center">

#  AIgriculture

**Raspberry Pi के लिए ओपन-सोर्स स्मार्ट फार्म सिस्टम।**
मिट्टी की नमी पर नज़र रखें, सिंचाई स्वचालित करें, रोगों का पता लगाएं और AI से बात करें — सब कुछ एक वेब डैशबोर्ड से।

[![English](https://img.shields.io/badge/lang-English-blue?style=for-the-badge)](../../README.md)
[![日本語](https://img.shields.io/badge/lang-日本語-red?style=for-the-badge)](../ja/README.md)
[![हिन्दी](https://img.shields.io/badge/lang-हिन्दी-orange?style=for-the-badge)](README.md)
[![Русский](https://img.shields.io/badge/lang-Русский-green?style=for-the-badge)](../ru/README.md)
[![中文](https://img.shields.io/badge/lang-中文-red?style=for-the-badge)](../zh/README.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-Pi%20native%20(3.13)-blue.svg)](https://www.python.org/downloads/)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-4%20%7C%205-c51a4a)](https://www.raspberrypi.com/)

</div>

---

![फार्म दृश्य](../assets/small_prototype.jpeg)

---

## यह क्या करता है

| उप-तंत्र | आपको क्या मिलता है |
|----------|---------------------|
| **सिंचाई** | जितने पौधे चाहें उतने के लिए बर्स्ट इरीगेशन, ऑटो-मोड के साथ (45 % नमी पर शुरू, 65 % पर रुकना, 70 % पर हार्डलॉक) |
| **FarmMonitor** | समय-समय पर YOLO स्कैन — रोग (5 क्लास) और पकने की अवस्था (5 स्टेज), पकड़ने पर ईमेल अलर्ट |
| **सिक्योरिटी कैमरा** | रियल-टाइम मानव/जानवर डिटेक्शन, डुअल-बज़र सायरन, डैशबोर्ड में MJPEG स्ट्रीम |
| **FLORA AI** | मल्टी-प्रोवाइडर चैट असिस्टेंट (Groq / Cerebras / Mistral / Gemini), फार्म टूल कॉल, ऑफ़लाइन फॉलबैक |
| **Meshtastic** | LoRa ब्रिज — FLORA आपकी मेश नेटवर्क पर किसी भी चैनल या DM का जवाब देती है |
| **डैशबोर्ड** | डार्क थीम सिंगल-पेज ऐप: ओवरव्यू, कैमरा, AI चैट, इवेंट लॉग, सेटिंग्स |

रिपो में **दो एंट्री पॉइंट** हैं — अपने हार्डवेयर के हिसाब से चुनें:

| स्क्रिप्ट | कब लें | सिक्योरिटी कैमरा इंजन |
|-----------|--------|------------------------|
| **`python main.py`** | डिफ़ॉल्ट। किसी भी Raspberry Pi (4 / 5) या लैपटॉप पर चलता है। | Ultralytics YOLOv8s, CPU पर frame-skip — nano के मुक़ाबले व्यक्ति / भालू / गाय / हाथी पर बेहतर डिटेक्शन, Pi 5 पर रियल-टाइम। |
| **`python main-hailo.py`** | जब Hailo-10H AI HAT लगा हो। | Hailo HEF पाइपलाइन — ~10× तेज़ इन्फरेंस। |

बाकी सब — डैशबोर्ड, लॉगिन, FLORA, FarmMonitor, सिंचाई, ईमेल अलर्ट, स्टोरेज, Meshtastic — दोनों स्क्रिप्ट्स में **एक जैसा** है। फर्क सिर्फ़ सिक्योरिटी कैमरा के इन्फरेंस इंजन का है।

---

## 🛠️ हार्डवेयर — शुरुआती / टेस्टिंग बिल्ड

असली फार्म नहीं है? **कोई बात नहीं।** यह सबसे छोटी किट है जो AIgriculture को डेस्क-टॉप प्रोटोटाइप बना देती है। नीचे की हर पंक्ति शुरुआती-अनुकूल विकल्प है।

| # | कंपोनेंट | क्यों ज़रूरी है | शुरुआती टिप |
|---|---------|-----------------|----------------|
| 1 | **Raspberry Pi 4 / 5** (4 GB+, 8 GB सुझाव)<br><img src="../assets/hardware/Raspberrypi_5.png" width="240"> | पूरा सिस्टम — डैशबोर्ड, AI, सिंचाई लॉजिक — यही चलाता है। | Pi 5 सबसे तेज़ है, पर Pi 4 (2 GB) भी काम करेगा। **Raspberry Pi OS Bookworm 64-bit** फ्लैश करें। |
| 2 | **ADS1115 16-bit I²C ADC**<br><img src="../assets/hardware/adc_module.png" width="240"> | Pi में एनालॉग इनपुट नहीं होता। कैपेसिटिव नमी सेंसर एनालॉग होते हैं, ADC उन्हें संख्याओं में बदलता है। | एक ADS1115 = 4 सेंसर। जितना चाहिए उतना लगाएं — 16 पौधों के लिए **चार** (`0x48`-`0x4B`), या और भी बस लगा कर बड़े फार्म तक। |
| 3 | **कैपेसिटिव मिट्टी नमी सेंसर**<br><img src="../assets/hardware/moisture_sensor.png" width="240"> | मिट्टी कितनी गीली है, ये पढ़ता है — ऑटो-सिंचाई का इनपुट। | **कैपेसिटिव** (पीला PCB) ही लें, सस्ते रेज़िस्टिव वाले हफ़्तों में जंग पकड़ लेते हैं। हर पौधे के लिए एक। |
| 4 | **8-चैनल रिले बोर्ड** (active-LOW, opto-isolated)<br><img src="../assets/hardware/relay_module.png" width="240"> | पंपों को ON/OFF करने देता है। Pi ख़ुद से पंप की पावर नहीं दे सकता। | **5V ट्रिगर, ऑप्टो-आइसोलेटेड** लिखा हो — वरना 3.3V पिन से काम नहीं करेगा। |
| 5 | **छोटा 5V या 12V DC वॉटर पंप**<br><img src="../assets/hardware/water_pump.png" width="240"> | असली में पौधे को पानी यही देता है। | हर पौधे के लिए एक। **हमेशा अलग पावर सप्लाई दें, Pi के 5V रेल से कभी नहीं।** Pi सिर्फ़ रिले कंट्रोल करता है। |
| 6 | **Raspberry Pi कैमरा (CSI)** *या* **USB वेबकैम**<br><img src="../assets/hardware/pi-camera.jpeg" width="200"> &nbsp; <img src="../assets/hardware/usb_camera.png" width="200"> | एक से FarmMonitor रोग/पकने का स्कैन, दूसरे से सिक्योरिटी कैमरा। | एक कैमरे से भी शुरू कर सकते हैं — `--security-camera` पास करें, `--farm-camera` छोड़ दें। RTSP IP कैमरा भी चलेगा। |
| 7 | **ब्रेडबोर्ड + जंपर वायर**<br><img src="../assets/hardware/breadboard_and_jumper_wires.png" width="240"> | बिना सोल्डरिंग के सब जोड़ने के लिए। | सेंसर से ADC के लिए female-to-female, ADC से Pi के लिए male-to-female जंपर लें। |
| **+** | **Hailo-10H AI HAT** *(वैकल्पिक, तेज़ विज़न)*<br><img src="../assets/hardware/hailo10h_optional.png" width="240"> | हार्डवेयर-एक्सेलरेटेड YOLO इन्फरेंस। रोग/पकने स्कैन का समय बहुत कम। | **शुरुआती बिल्ड में छोड़ें।** साधारण Pi पर CPU रास्ता भी अच्छा चलता है। बस तेज़ चाहिए तब लें। |
| **+** | **Meshtastic LoRa रेडियो** *(वैकल्पिक, ऑफ़-ग्रिड चैट)*<br><img src="../assets/hardware/LORA_chip_with_433hz_antenna.png" width="240"> | Wi-Fi की पहुँच से बाहर हों तब भी LoRa मेश पर FLORA से बात करें। | वैकल्पिक। Heltec / LilyGo बोर्ड और 433 / 868 / 915 MHz एंटीना चलेंगे। केवल वेब UI काफ़ी है तो छोड़ दें। |

**मिनिमम टेस्टिंग बिल्ड** (केवल डेस्क पर डैशबोर्ड चलाने के लिए):
> 1 × Pi · 1 × ADS1115 · 1 × नमी सेंसर · 1 × USB कैमरा। बस। न रिले, न पंप, न Hailo। डैशबोर्ड चलने पर "+ Add sensors" बटन से और बढ़ा सकते हैं।

---

## 🚀 जल्दी शुरुआत

```bash
git clone https://github.com/darkphantom-gamer/AIgriculture.git
cd AIgriculture
cp .env.example .env            # फिर .env एडिट करें (अगला सेक्शन देखें)
python main.py
```

ब्राउज़र में `http://<pi-ip>:8000` खोलें।

> **लैपटॉप / Non-Pi पर चला रहे हैं?** चलेगा। हार्डवेयर न होने पर GPIO/I2C ख़ामोशी से no-op कर देते हैं — डैशबोर्ड, AI चैट, और (USB/नेटवर्क) कैमरे फिर भी काम करेंगे।

> **नेटिव इंस्टॉल चाहिए?**
> ```bash
> pip install -r requirements.txt --break-system-packages
> python main.py
> ```

---

## 🔑 आपको अपने क्रेडेंशियल डालने हैं

**इस रिपो में कोई असली API की, पासवर्ड या ईमेल नहीं है — यह डिज़ाइन से ऐसा है।**
`cp .env.example .env` के बाद `.env` खोलें और अपनी जानकारी डालें:

| `.env` में | क्या डालें | कहाँ से लें |
|------------|-------------|-------------|
| `ADMIN_USER` | जो भी डैशबोर्ड यूज़रनेम चाहें | (आपका चुनाव) |
| `ADMIN_PASS` | मज़बूत पासवर्ड | (आपका चुनाव) |
| `GROQ_API_KEY` | आपकी Groq की (सुझाव — तेज़, मुफ़्त) | https://console.groq.com |
| `CEREBRAS_API_KEY` | आपकी Cerebras की (वैकल्पिक) | https://cloud.cerebras.ai |
| `MISTRAL_API_KEY` | आपकी Mistral की (वैकल्पिक) | https://console.mistral.ai |
| `GEMINI_API_KEY` | आपकी Google AI Studio की (वैकल्पिक) | https://aistudio.google.com |

**कोई एक** AI प्रोवाइडर सेट करें तो FLORA पूरी टूल-कॉलिंग चैट देती है। सब खाली रहें तब भी FLORA कीवर्ड रूटिंग से ऑफ़लाइन काम करती है।

**ईमेल अलर्ट** (FarmMonitor रोग सूचना, FLORA रिपोर्ट) चाहिए तो:
```bash
cp config.example.yaml config.yaml      # फिर config.yaml एडिट करें
```

`config.yaml` में अपना SMTP डालें — Gmail (*app password* के साथ), Hostinger, स्कूल मेल, कुछ भी जो SMTP बोलता हो:

```yaml
smtp:
  host: smtp.gmail.com          # या smtp.hostinger.com, smtp.office365.com, आदि
  port: 587
  email: you@your-domain.com    # आपका असली ईमेल
  password: your-app-password   # साधारण पासवर्ड नहीं — app password
  from_email: you@your-domain.com
notifications:
  to_email: alerts@your-domain.com
```

> **Gmail टिप:** 2-Step Verification चालू करें, फिर https://myaccount.google.com/apppasswords से **App Password** बनाएं और पेस्ट करें। साधारण पासवर्ड को SMTP स्वीकार नहीं करता।

`.env` और `config.yaml` दोनों git-ignored हैं — आपके राज़ रिपो में नहीं जाते।

---

## 🔌 वायरिंग (एक फ़ाइल बदल कर अपना बोर्ड फिट करें)

डिफ़ॉल्ट पिन मैप (`main.py` के साथ आता है):

| कंपोनेंट | डिफ़ॉल्ट BCM पिन |
|---------|------------------|
| 8 पंप रिले (पौधे A → H) | `17, 27, 22, 23, 5, 6, 13, 19` (active LOW) |
| 2 बज़र सायरन | `18, 12` (2700 Hz) |
| 8 नमी सेंसर | ADS1115 × 2, I²C `0x48` और `0x49` पर |
| I²C बस | `/dev/i2c-1` |
| GPIO चिप | `/dev/gpiochip0` (Pi 5 के लिए `4` ऑटो-ट्राय) |

**अलग पिन चाहिए?** Python छूने की ज़रूरत **नहीं**:

```bash
cp wiring.example.yaml wiring.yaml      # फिर wiring.yaml एडिट करें
python main.py
```

`wiring.yaml` से कोई भी पिन, active-high/low, बज़र की संख्या या फ्रीक्वेंसी, और नमी कैलिब्रेशन बिना कोड छुए बदलें।

---

## 📡 Meshtastic LoRa ब्रिज (इन-प्रोसेस)

`.env` में `MESH_ENABLED=true` सेट करें — `main.py` और `main-hailo.py` दोनों Meshtastic ↔ FLORA ब्रिज को **एक ही प्रोसेस के अंदर** स्टार्ट करते हैं। अलग सर्विस चलाने की ज़रूरत नहीं। ब्रिज:

- लोकल `meshtasticd` से TCP कनेक्ट होता है (डिफ़ॉल्ट `localhost:4403`)
- किसी भी चैनल या DM पर सुनता है
- इन-प्रोसेस HTTP API से FLORA को मैसेज भेजता है
- जिस चैनल पर मैसेज आया उसी पर वापस जवाब देता है

<p align="center">
  <img src="../img/meshtastic-flora-proof.jpg" alt="Meshtastic ↔ FLORA असली LoRa चैट" width="520">
</p>

Meshtastic लाइब्रेरी न हो या कनेक्शन टूट जाए, ब्रिज सिर्फ़ चेतावनी लॉग करेगा — `main.py` चलता रहेगा, डैशबोर्ड कभी ब्लॉक नहीं होगा।

`MESH_*` के सारे विकल्प (allowed nodes, reply mode, channel filter) `.env.example` में हैं।

---

## ➕ रनटाइम पर और सेंसर जोड़ें

डैशबोर्ड के ऊपर-दाएँ कोने में (केवल एडमिन के लिए) **"+ Add sensors"** बटन है। क्लिक करते ही:

1. सभी ADS1115 पतों (`0x48`-`0x4B`) के सभी 4 चैनलों पर I²C बस स्कैन
2. वैध नमी रीडिंग देने वाले, अभी तक इस्तेमाल में न आने वाले चैनल खोजे जाते हैं
3. उन्हें नए पौधे के रूप में (`i`-`p` अक्षर, अधिकतम 16) रजिस्टर करके `.plants.json` में सेव कर दिया जाता है
4. पोलिंग तुरंत शुरू — रीस्टार्ट या कोड बदलाव की ज़रूरत नहीं

2-सेंसर टेस्टिंग बिल्ड से शुरू करके बाद में फार्म बढ़ाने पर बहुत काम आता है।

---

## डैशबोर्ड

![डैशबोर्ड स्थिति](../assets/dashboard_status.png)

पाँच टैब: **Overview** (लाइव नमी + पंप कंट्रोल), **Cameras** (MJPEG स्ट्रीम), **FLORA** (AI चैट), **Events** (अलर्ट लॉग), **Settings** (नोटिफिकेशन + सायरन)।

---

## FLORA AI असिस्टेंट

![FLORA प्रीव्यू](../assets/FLORA_preview.jpeg)

FLORA साधारण भाषा के आदेश समझती है:

- *"पौधे A को पानी दो"* → बर्स्ट सिंचाई शुरू
- *"सभी पौधों की नमी क्या है?"* → सारे सेंसर पढ़ती है
- *"C का पंप बंद करो"* → पंप C बंद
- *"क्या कोई रोग पाया गया?"* → नवीनतम FarmMonitor स्कैन देखती है

कोई API की न हो तब भी FLORA कीवर्ड रूटिंग से पूरी तरह ऑफ़लाइन काम करती है।

### आर्किटेक्चर

| लेयर | भूमिका |
|------|--------|
| ![Layer 1](../assets/FLORA_first_layer_Architecture.png) | प्रोवाइडर रूटिंग + फॉलबैक |
| ![Layer 2](../assets/FLORA_Second_layer_Architecture.png) | टूल डिस्पैच (सेंसर, पंप, कैमरा, शेड्यूलर) |
| ![Layer 3](../assets/FLORA_Third_Lasyer_Architecture.png) | FLORA की रीज़निंग और इंटीग्रेशन |

---

## FarmMonitor

![FarmMonitor आर्किटेक्चर](../assets/Farm_Monitor_Core_Architecture.png)

शेड्यूल पर पूरे खेत की स्कैन चलाता है। फ्रेम के बैच लेता है, धुंधले हटाता है, फिर रोग और पकने की डिटेक्शन करता है।

![FarmMonitor परिणाम](../assets/Farm_Monitor_Result.png)

परिणाम `runtime/farmmonitor/` में JSON + JPEG के रूप में सेव होते हैं। रोग दिखने पर और SMTP सेट हो तो ईमेल अलर्ट जाता है।

---

## सिक्योरिटी कैमरा

![सिक्योरिटी कैमरा परिणाम](../assets/Security_camera_result.png)

फ्रेम-स्किप इन्फरेंस (हर N फ्रेम) और क्लास allow-list से CPU हल्का रहता है। ख़तरा मिले तो सायरन 8 सेकंड बजती है और स्नैपशॉट सेव होता है।

---

## Meshtastic LoRa ब्रिज

![Meshtastic](../assets/MEshtastic.png)

`.env` में `MESH_ENABLED=true` करें और `MESH_HOST` को अपने नोड पर सेट करें। FLORA किसी भी चैनल या DM पर सुनती है और भेजने वाले को ही उत्तर देती है — पूरी तरह ऑफ़-ग्रिड चलता है।

---

## स्टोरेज

![Storage](../assets/Storage_Data_screenshot.png)

सभी कैप्चर फ्रेम, फ़ार्म स्कैन और सिक्योरिटी स्नैपशॉट डैशबोर्ड के Events टैब और स्टोरेज API से ब्राउज़ किए जा सकते हैं।

---

## कैमरा विकल्प

**सिक्योरिटी कैमरा** और **FarmMonitor कैमरा** (रोग / पकने स्कैन) — दोनों एक ही तरह के सोर्स लेते हैं: RPi CSI, USB, RTSP IP, या HTTP-MJPEG।

| कैमरा | CLI फ़्लैग | Env वैरिएबल |
|------|-----------|------------|
| सिक्योरिटी (इंट्रूज़न) | `--security-cam <SRC>` | `SECURITY_CAMERA_SOURCE` |
| FarmMonitor (रोग/पकना) | `--farm-cam <SRC>` | `FARM_MONITOR_CAMERA` |
| RPi CSI (FarmMonitor शॉर्टकट) | `--use-rpicam` | — |

```bash
# Raspberry Pi CSI कैमरा (सिक्योरिटी)
python main.py --security-cam rpi

# Raspberry Pi CSI कैमरा (FarmMonitor — picamera2 पाथ)
python main.py --use-rpicam

# Raspberry Pi CSI कैमरा (FarmMonitor — OpenCV पाथ)
python main.py --farm-cam rpi

# दो USB कैमरे — एक-एक
python main.py --security-cam /dev/video0 --farm-cam /dev/video1

# IP / RTSP कैमरा (दोनों तरफ चलता है)
python main.py --security-cam rtsp://user:pass@192.168.1.10/live
python main.py --farm-cam   rtsp://user:pass@192.168.1.10/live

# HTTP-MJPEG IP कैमरा (एक ही URL दोनों कैमरों के लिए — हार्डवेयर के बिना टेस्ट करने के लिए)
python main.py --security-cam http://camera.example/cam.cgi \
               --farm-cam   http://camera.example/cam.cgi
```

दोनों फ़्लैग्स ये सोर्स लेते हैं: `rpi` / `csi` (RPi CSI), `/dev/videoN` (USB), इंडेक्स नंबर, `rtsp://…` (IP RTSP), `http://…` (IP MJPEG)। कोड बदलने की ज़रूरत नहीं — फ़्लैग बदलिए।

बिना किसी कैमरे के भी डैशबोर्ड, FLORA, सिंचाई, सेंसर एक्सपैंशन टेस्ट कर सकते हैं:

```bash
python main.py            # सिक्योरिटी कैमरा बंद; FarmMonitor "no camera" लॉग करेगा
```

---

## 🧠 अपना ML मॉडल लगाएं (कोई भी फ़सल, सिर्फ़ स्ट्रॉबेरी नहीं)

AIgriculture फ़सल-अग्नोस्टिक है। टमाटर, आम, मिर्च, अंगूर — जो भी उगाते हैं उस पर YOLOv8 ट्रेन कीजिए, वज़न `Models/` में डालिए, env वैरिएबल पॉइंट कीजिए। कोड बदलना नहीं पड़ेगा।

```bash
# 1. अपने ट्रेन किए हुए वज़न Models/ में डालिए
cp my_tomato_disease.pt    Models/Tomato_disease.pt
cp my_tomato_ripeness.pt   Models/Tomato_ripeness.pt

# 2. AIgriculture को बताइए कि इन्हें इस्तेमाल करे (.env में, या इनलाइन)
DISEASE_MODEL_PATH=Models/Tomato_disease.pt \
RIPENESS_MODEL_PATH=Models/Tomato_ripeness.pt \
python main.py
```

क्लास नाम और रंगों के लिए लेबल JSON डुप्लिकेट कीजिए:

```bash
cp farm_monitor_disease_labels.json    farm_monitor_tomato_disease_labels.json
cp farm_monitor_ripeness_labels.json   farm_monitor_tomato_ripeness_labels.json
# JSON में अपने मॉडल के क्लास नाम भरिए, फिर पॉइंट कीजिए:
DISEASE_LABELS_PATH=farm_monitor_tomato_disease_labels.json \
RIPENESS_LABELS_PATH=farm_monitor_tomato_ripeness_labels.json \
python main.py
```

**सिक्योरिटी कैमरा** के लिए — CPU बिल्ड में कोई भी Ultralytics वज़न (`SECURITY_MODEL=Models/yolov8m.pt`). Hailo बिल्ड (`main-hailo.py`) में `.hef` मॉडल — `PLANTWATCH_SECURITY_HEF` को `Models/` की फ़ाइल पर पॉइंट कीजिए।

बंडल किए गए `Disease_detect.pt` और `Ripeness_detect.pt` स्ट्रॉबेरी के लिए ट्यून किए हैं — सिर्फ़ शुरुआत है, कठोर आवश्यकता नहीं।

---

## Hailo (वैकल्पिक एक्सेलरेटर)

डिफ़ॉल्ट CPU पाथ (`main.py`) हर Pi 4 / 5 पर चलता है। अगर आपके पास **Hailo-10H AI HAT** है, पहले HailoRT और Hailo Apps इंस्टॉल करें, फिर Hailo बिल्ड चलाएं:

```bash
python main-hailo.py --security-cam /dev/video0
```

`main-hailo.py` और `main.py` का डैशबोर्ड, लॉगिन, FLORA, FarmMonitor, सिंचाई, Meshtastic, स्टोरेज, ईमेल अलर्ट — सब 100% एक ही है। फ़र्क़ बस इतना है कि सिक्योरिटी कैमरा इन्फरेंस CPU YOLO की जगह Hailo HEF पर चलती है — आमतौर पर ~10× तेज़।

---

## CLI रिफरेंस

```
python main.py [options]            # CPU बिल्ड (डिफ़ॉल्ट)
python main-hailo.py [options]      # Hailo HAT बिल्ड

  --security-cam SRC  इंट्रूज़न डिटेक्शन के लिए कैमरा
                      rpi | csi | /dev/videoN | <index> | rtsp://… | http://…
  --farm-cam     SRC  FarmMonitor के लिए कैमरा (रोग / पकने स्कैन)
                      rpi | csi | /dev/videoN | <index> | rtsp://… | http://…
  --use-rpicam        FarmMonitor के लिए picamera2 (libcamera) कैप्चर पाथ
```

एनवायरनमेंट वैरिएबल (`.env.example` देखें): `SECURITY_FRAME_SKIP`, `SECURITY_IMGSZ`, `SECURITY_MODEL`, `FARM_MONITOR_CAMERA`, `DISEASE_MODEL_PATH`, `RIPENESS_MODEL_PATH`, `DISEASE_LABELS_PATH`, `RIPENESS_LABELS_PATH`, `PLANTWATCH_SECURITY_HEF` (Hailo)।

---

## प्रोजेक्ट संरचना

```
AIgriculture/
├── main.py                             # CPU बिल्ड: डैशबोर्ड + सेंसर + सिंचाई + CPU YOLO
├── main-hailo.py                       # Hailo बिल्ड: वही + Hailo HEF सिक्योरिटी कैम
│
├── design/                             # ── फ्रंट-एंड पेज (थीम + UI) ──
│   ├── dashboard.html                  # डैशबोर्ड (सिंगल-पेज ऐप)
│   └── login.html                      # लॉगिन स्क्रीन
│
├── assets/                             # ── डैशबोर्ड के स्टैटिक इमेज / ऑडियो ──
│   ├── farmer.png                      # डिफ़ॉल्ट यूज़र अवतार
│   ├── low-cortisol.png                # मूड कार्ड इमेज
│   ├── test_drive_avatar.png           # डेमो अवतार
│   ├── agrisense-favicon.svg           # फ़ेविकॉन
│   └── threat.mp3                      # सायरन साउंड
│
├── Models/                             # ── ML वज़न (किसी भी फ़सल के लिए स्वैप करें) ──
│   ├── Disease_detect.pt               # YOLOv8 रोग डिटेक्टर (डिफ़ॉल्ट स्ट्रॉबेरी)
│   ├── Ripeness_detect.pt              # YOLOv8 पकने डिटेक्टर (डिफ़ॉल्ट स्ट्रॉबेरी)
│   ├── Disease_detect.hef              # Hailo HEF (Hailo बिल्ड के लिए वैकल्पिक)
│   └── yolov8*.pt                      # ऑटो-डाउनलोड सिक्योरिटी वज़न (gitignored)
│
├── farm_monitor_designer_email.py      # ब्रांडेड अलर्ट ईमेल टेम्पलेट
├── farm_monitor_pt_scan.py             # रोग + पकने .pt स्कैनर
├── farm_monitor_disease_labels.json    # रोग YOLO क्लास लेबल
├── farm_monitor_ripeness_labels.json   # पकने YOLO क्लास लेबल
├── flora_agent.py / flora_config.py    # FLORA AI असिस्टेंट
├── flora_report.py / flora_scheduler.py / flora_tools.py
├── meshtastic_flora_bridge.py          # LoRa ब्रिज
│
├── docs/assets/                        # README में उपयोग की गई इमेज
├── docs/{ja,hi,ru,zh}/README.md        # अनुवादित READMEs
│
├── .env.example                        # ← .env में कॉपी करके एडिट
├── config.example.yaml                 # ← config.yaml में कॉपी (ईमेल)
├── wiring.example.yaml                 # ← wiring.yaml में कॉपी (कस्टम पिन)
└── requirements.txt
```

`design/`, `assets/`, और `Models/` में सब **स्वैप करने योग्य** है। env वैरिएबल से पाथ ओवरराइड करें, या नई फ़ाइलें उसी नाम से डाल दें।

---

## लेखक

**The Great Himkamal** ([@darkphantom-gamer](https://github.com/darkphantom-gamer))
असली हार्डवेयर पर बनाया और मेंटेन किया हुआ — एक स्ट्रॉबेरी फार्म जो Raspberry Pi 5 पर चलता है।
योगदान, फ़सल मॉडल, और अनुवाद का स्वागत है।

---

## लाइसेंस

MIT — [LICENSE](LICENSE) देखें।
