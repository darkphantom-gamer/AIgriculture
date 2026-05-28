<div align="center">

# 🌱 AIgriculture

**Raspberry Pi के लिए ओपन-सोर्स स्मार्ट फार्म सिस्टम**
मिट्टी की नमी की निगरानी करें, सिंचाई स्वचालित करें, बीमारी का पता लगाएं, और AI से बात करें — सब कुछ एक वेब डैशबोर्ड से।

[![English](https://img.shields.io/badge/lang-English-blue?style=for-the-badge)](README.md)
[![日本語](https://img.shields.io/badge/lang-日本語-red?style=for-the-badge)](README.ja.md)
[![हिन्दी](https://img.shields.io/badge/lang-हिन्दी-orange?style=for-the-badge)](README.hi.md)
[![Русский](https://img.shields.io/badge/lang-Русский-green?style=for-the-badge)](README.ru.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-4%20%7C%205-c51a4a)](https://www.raspberrypi.com/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ed)](https://docs.docker.com/)

</div>

---

![फार्म दृश्य](docs/assets/big_farm.jpeg)

---

## क्या-क्या मिलता है

| सबसिस्टम | विवरण |
|----------|-------|
| **सिंचाई** | 8-पौधों की बर्स्ट सिंचाई — 45% पर चालू, 65% पर बंद, 70% हार्डलॉक |
| **FarmMonitor** | YOLO से नियमित स्कैन — 5 बीमारियाँ और 5 पकने की अवस्थाएं; ईमेल अलर्ट |
| **सुरक्षा कैमरा** | रियल-टाइम व्यक्ति/पशु पहचान, दोहरा बजर साइरन, MJPEG स्ट्रीम |
| **FLORA AI** | Groq / Cerebras / Mistral / Gemini चैट असिस्टेंट; ऑफलाइन सपोर्ट |
| **Meshtastic** | LoRa ब्रिज — मेश नेटवर्क से FLORA से बात करें |
| **डैशबोर्ड** | डार्क-थीम सिंगल-पेज ऐप (अवलोकन, कैमरा, AI, इवेंट्स, सेटिंग्स) |

---

## हार्डवेयर

![प्रोटोटाइप](docs/assets/small_prototype.jpeg)

| घटक | विवरण |
|-----|-------|
| Raspberry Pi 4/5 | 2GB+ RAM, 64-bit OS Bookworm |
| ADS1115 × 2 | I2C ADC (0x48, 0x49) — 8 नमी चैनल |
| 8-चैनल रिले बोर्ड | Active LOW, BCM 17 27 22 23 5 6 13 19 |
| बजर × 2 | BCM 18, 12 (2700 Hz) |
| Pi Camera × 2 | CSI — सुरक्षा (csi:0) + FarmMonitor (csi:1) |
| *(वैकल्पिक)* Hailo-8 M.2 | हार्डवेयर AI एक्सेलेरेटर |

पूरा वायरिंग नक्शा [`aigriculture.txt`](aigriculture.txt) में है।

---

## 🚀 त्वरित शुरुआत

```bash
git clone https://github.com/darkphantom-gamer/AIgriculture.git
cd AIgriculture
cp .env.example .env   # फिर .env को संपादित करें (नीचे देखें)
docker compose up -d
```

ब्राउज़र में `http://<pi-ip>:8000` खोलें।

> Pi नहीं है? कोई बात नहीं। GPIO और I2C चुपचाप no-op हो जाते हैं — डैशबोर्ड, AI चैट, और USB/नेटवर्क कैमरे लैपटॉप पर भी काम करते हैं।

नेटिव इंस्टॉल, systemd सेवा और Hailo के लिए [docs/SETUP.md](docs/SETUP.md) देखें।

---

## 🔑 अपनी क्रेडेंशियल खुद जोड़ें

**इस रिपॉजिटरी में कोई असली API कुंजी, पासवर्ड या ईमेल नहीं है — यह जानबूझकर है।**
`cp .env.example .env` के बाद `.env` खोलें और अपनी जानकारी भरें:

| `.env` फ़ील्ड | क्या भरें | कहाँ से लें |
|---------------|---------|-----------|
| `ADMIN_USER` | डैशबोर्ड यूज़रनेम | (आप तय करें) |
| `ADMIN_PASS` | मज़बूत पासवर्ड | (आप तय करें) — खाली छोड़ने पर पहली बार रैंडम पासवर्ड कंसोल पर दिखेगा |
| `GROQ_API_KEY` | Groq कुंजी (सिफ़ारिश की गई, मुफ़्त, तेज़) | https://console.groq.com |
| `CEREBRAS_API_KEY` | Cerebras कुंजी (वैकल्पिक) | https://cloud.cerebras.ai |
| `MISTRAL_API_KEY` | Mistral कुंजी (वैकल्पिक) | https://console.mistral.ai |
| `GEMINI_API_KEY` | Google AI Studio कुंजी (वैकल्पिक) | https://aistudio.google.com |

**किसी एक भी** AI प्रदाता की कुंजी जोड़ने पर FLORA फ़ुल टूल-यूज़ चैट करता है। सब खाली रखें तो FLORA कीवर्ड-आधारित ऑफ़लाइन मोड में काम करता है।

**ईमेल अलर्ट** के लिए (FarmMonitor बीमारी अलर्ट / FLORA रिपोर्ट):
```bash
cp config.example.yaml config.yaml      # फिर संपादित करें
```

`config.yaml` में अपना SMTP भरें — Gmail (**ऐप पासवर्ड** के साथ), Hostinger, या कोई भी SMTP सेवा:

```yaml
smtp:
  host: smtp.gmail.com
  port: 587
  email: you@your-domain.com
  password: your-app-password   # सामान्य पासवर्ड नहीं — ऐप पासवर्ड
  from_email: you@your-domain.com
notifications:
  to_email: alerts@your-domain.com
```

> **Gmail सलाह:** 2-स्टेप वेरिफ़िकेशन चालू करें, फिर https://myaccount.google.com/apppasswords से App Password बनाएँ।

`.env` और `config.yaml` दोनों `.gitignore` में हैं — आपके असली पासवर्ड कभी रेपो में नहीं जाएंगे।

---

## 🔌 वायरिंग (एक फ़ाइल बदलें)

डिफ़ॉल्ट पिन मैप:

| भाग | डिफ़ॉल्ट BCM पिन |
|----|------|
| 8 पंप रिले | `17, 27, 22, 23, 5, 6, 13, 19` (Active LOW) |
| 2 बजर | `18, 12` (2700 Hz) |
| नमी सेंसर | ADS1115 × 2, `0x48` व `0x49` पर |

**अलग पिन उपयोग के लिए Python छूना ज़रूरी नहीं:**

```bash
cp wiring.example.yaml wiring.yaml      # फिर संपादित करें
docker compose up -d --force-recreate
```

---

## डैशबोर्ड

![डैशबोर्ड](docs/assets/dashboard_status.png)

पाँच टैब: **अवलोकन** (लाइव नमी + पंप नियंत्रण), **कैमरा** (MJPEG स्ट्रीम), **FLORA** (AI चैट), **इवेंट्स** (अलर्ट लॉग), **सेटिंग्स** (नोटिफिकेशन + साइरन)।

---

## FLORA AI असिस्टेंट

![FLORA](docs/assets/FLORA_preview.jpeg)

FLORA प्राकृतिक भाषा के आदेश समझती है:

- *"पौधे A को पानी दो"* → बर्स्ट सिंचाई शुरू
- *"सभी पौधों की नमी बताओ"* → सभी सेंसर पढ़ता है
- *"कोई बीमारी मिली है क्या?"* → ताजा FarmMonitor स्कैन जाँचता है

API कुंजी के बिना भी FLORA कीवर्ड रूल्स से ऑफलाइन काम करती है।

---

## FarmMonitor

![FarmMonitor](docs/assets/Farm_Monitor_Core_Architecture.png)

निर्धारित समय पर पूरे खेत का स्कैन — धुंधले फ्रेम हटाकर बीमारी और पकने का विश्लेषण।

![परिणाम](docs/assets/Farm_Monitor_Result.png)

---

## कैमरा विकल्प

```bash
# Pi CSI कैमरा
python -m aigriculture --security-camera csi:0 --farm-camera csi:1

# USB कैमरा
python -m aigriculture --security-camera /dev/video0

# नेटवर्क RTSP कैमरा
python -m aigriculture --security-camera rtsp://192.168.1.10/live
```

---

## लाइसेंस

MIT — [LICENSE](LICENSE) देखें।
