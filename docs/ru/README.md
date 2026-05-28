<div align="center">

# 🌱 AIgriculture

**Система умной фермы с открытым исходным кодом для Raspberry Pi.**
Следите за влажностью почвы, автоматизируйте полив, обнаруживайте болезни и общайтесь со своей фермой с помощью ИИ — всё это с одной веб-панели.

[![English](https://img.shields.io/badge/lang-English-blue?style=for-the-badge)](../../README.md)
[![日本語](https://img.shields.io/badge/lang-日本語-red?style=for-the-badge)](../ja/README.md)
[![हिन्दी](https://img.shields.io/badge/lang-हिन्दी-orange?style=for-the-badge)](../hi/README.md)
[![Русский](https://img.shields.io/badge/lang-Русский-green?style=for-the-badge)](README.md)
[![中文](https://img.shields.io/badge/lang-中文-red?style=for-the-badge)](../zh/README.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-Pi%20native%20(3.13)-blue.svg)](https://www.python.org/downloads/)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-4%20%7C%205-c51a4a)](https://www.raspberrypi.com/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ed)](https://docs.docker.com/)

</div>

---

![Обзор фермы](../assets/small_prototype.jpeg)

---

## Что это умеет

| Подсистема | Что вы получаете |
|------------|-------------------|
| **Полив** | Импульсный полив на 8 растений в автоматическом режиме (запуск при 45 %, остановка при 65 %, жёсткая блокировка при 70 %) |
| **FarmMonitor** | Периодический YOLO-скан: болезни (5 классов) и стадии созревания (5 стадий), e-mail при обнаружении |
| **Камера безопасности** | Обнаружение людей/животных в реальном времени, двойная сирена, MJPEG-стрим в дашборде |
| **FLORA AI** | Мульти-провайдерный чат-ассистент (Groq / Cerebras / Mistral / Gemini), вызов инструментов фермы, офлайн-режим |
| **Meshtastic** | LoRa-мост — FLORA отвечает в любом канале или ЛС вашей mesh-сети |
| **Дашборд** | Одностраничное приложение в тёмной теме: обзор, камеры, ИИ-чат, журнал событий, настройки |

---

## 🛠️ Железо — сборка для новичков / для теста

Нет настоящей фермы? **Не нужна.** Вот минимальный набор, который превращает AIgriculture в работающий настольный прототип. Каждая строка ниже — это понятная новичку замена для полноразмерной сборки.

| # | Компонент | Зачем нужно | Совет новичку |
|---|-----------|-------------|----------------|
| 1 | **Raspberry Pi 4 / 5** (4 ГБ+, рекомендуется 8 ГБ)<br><img src="../assets/hardware/Raspberrypi_5.png" width="240"> | На нём работает всё — дашборд, ИИ, логика полива. | Pi 5 быстрее, но Pi 4 (2 ГБ) тоже подойдёт. Прошейте **Raspberry Pi OS Bookworm 64-bit**. |
| 2 | **ADS1115 16-битный I²C АЦП**<br><img src="../assets/hardware/adc_module.png" width="240"> | У Pi нет аналоговых входов, а ёмкостные датчики аналоговые — АЦП переводит их в числа. | Один ADS1115 = 4 датчика. Для стандартной сборки на 8 растений берите **два** (`0x48` + `0x49`), до **четырёх** (`0x48`-`0x4B`) для 16 растений. |
| 3 | **Ёмкостный датчик влажности почвы**<br><img src="../assets/hardware/moisture_sensor.png" width="240"> | Измеряет влажность почвы — это вход автоматического полива. | Только **ёмкостный** (жёлтая плата), дешёвые резистивные коррозируют за пару недель. По одному на растение. |
| 4 | **8-канальная плата реле** (active-LOW, оптоизолированная)<br><img src="../assets/hardware/relay_module.png" width="240"> | Позволяет Pi включать/выключать насосы. Pi сам не может питать насос. | Берите с пометкой **5V trigger, opto-isolated**, иначе с 3,3 В Pi работать не будет. |
| 5 | **Маленький водяной насос 5 В или 12 В DC**<br><img src="../assets/hardware/water_pump.png" width="240"> | Та самая штука, которая поливает растение. | По одному на растение. **Всегда питайте от отдельного БП, а не от 5V Pi.** Pi только управляет реле. |
| 6 | **Камера Raspberry Pi (CSI)** *или* **USB-веб-камера**<br><img src="../assets/hardware/pi-camera.jpeg" width="200"> &nbsp; <img src="../assets/hardware/usb_camera.png" width="200"> | Одна — для скана FarmMonitor, другая — для камеры безопасности. | Можно начать и с одной — передайте `--security-camera`, пропустите `--farm-camera`. RTSP IP-камеры тоже работают. |
| 7 | **Макетная плата + перемычки**<br><img src="../assets/hardware/breadboard_and_jumper_wires.png" width="240"> | Чтобы собрать всё без пайки. | Возьмите перемычки мама-мама для датчик→АЦП и мама-папа для АЦП→Pi. |
| **+** | **Hailo-10H AI HAT** *(опционально, ускоренный CV)*<br><img src="../assets/hardware/hailo10h_optional.png" width="240"> | Аппаратное ускорение YOLO. Заметно сокращает время сканов. | **Пропустите для сборки новичка.** На обычном Pi путь через CPU тоже работает нормально. Добавляйте Hailo только если нужно быстрее. |
| **+** | **Радио Meshtastic LoRa** *(опционально, чат вне сети)*<br><img src="../assets/hardware/LORA_chip_with_433hz_antenna.png" width="240"> | Общайтесь с FLORA вне зоны Wi-Fi через LoRa-mesh. | Опционально. Платы Heltec / LilyGo с антеннами 433 / 868 / 915 МГц работают. Пропустите, если хватит веб-интерфейса. |

**Минимальная тестовая сборка** (просто чтобы поиграть с дашбордом на столе):
> 1 × Pi · 1 × ADS1115 · 1 × датчик влажности · 1 × USB-камера. И всё. Никаких реле, насосов, Hailo. Дальше пользуйтесь кнопкой "+ Add sensors" прямо в дашборде.

---

## 🚀 Быстрый старт

```bash
git clone https://github.com/darkphantom-gamer/AIgriculture.git
cd AIgriculture
cp .env.example .env            # потом РЕДАКТИРУЙТЕ .env (см. следующий раздел)
docker compose up -d
```

Откройте `http://<pi-ip>:8000`.

> **Запускаете на ноутбуке / не на Pi?** Это тоже работает. GPIO и I2C тихо становятся «no-op», когда железа нет — вам доступны дашборд, ИИ-чат и USB / сетевые камеры.

> **Хотите нативную установку?**
> ```bash
> pip install -r requirements.txt --break-system-packages
> python plantwatch.py
> ```

---

## 🔑 Свои учётные данные — обязательно

**В репозитории нет реальных API-ключей, паролей и e-mail — так и задумано.**
После `cp .env.example .env` откройте `.env` и заполните своими значениями:

| В `.env` | Что положить | Где взять |
|----------|--------------|-----------|
| `ADMIN_USER` | Имя пользователя дашборда (на ваш выбор) | (вы решаете) |
| `ADMIN_PASS` | Стойкий пароль | (вы решаете) |
| `GROQ_API_KEY` | Ваш ключ Groq (рекомендуется — быстро и бесплатно) | https://console.groq.com |
| `CEREBRAS_API_KEY` | Ключ Cerebras (опционально) | https://cloud.cerebras.ai |
| `MISTRAL_API_KEY` | Ключ Mistral (опционально) | https://console.mistral.ai |
| `GEMINI_API_KEY` | Ключ Google AI Studio (опционально) | https://aistudio.google.com |

Установите **любого одного** провайдера — и FLORA получит полный чат с вызовом инструментов. Оставьте всё пустым — FLORA будет работать офлайн через ключевые слова.

Для **e-mail-уведомлений** (FarmMonitor, отчёты FLORA):
```bash
cp config.example.yaml config.yaml      # потом редактируйте config.yaml
```

В `config.yaml` укажите свой SMTP — Gmail (с *App Password*), Hostinger, школьная почта, что угодно:

```yaml
smtp:
  host: smtp.gmail.com          # или smtp.hostinger.com, smtp.office365.com и т. д.
  port: 587
  email: you@your-domain.com    # ваш реальный адрес
  password: your-app-password   # НЕ обычный пароль — именно App Password
  from_email: you@your-domain.com
notifications:
  to_email: alerts@your-domain.com
```

> **Совет по Gmail:** включите двухфакторную аутентификацию, затем создайте **App Password** на https://myaccount.google.com/apppasswords и вставьте его. Обычные пароли Gmail SMTP отклоняет.

`.env` и `config.yaml` оба в `.gitignore` — ваши реальные секреты не попадут в репозиторий.

---

## 🔌 Подключение (поменяйте один файл под свою плату)

Карта пинов по умолчанию (как поставляется в `plantwatch.py`):

| Компонент | BCM-пины по умолчанию |
|-----------|----------------------|
| 8 реле насосов (растения A → H) | `17, 27, 22, 23, 5, 6, 13, 19` (active LOW) |
| 2 пьезо-сирены | `18, 12` (2700 Гц) |
| 8 датчиков влажности | ADS1115 × 2 на I²C `0x48` и `0x49` |
| Шина I²C | `/dev/i2c-1` |
| GPIO-чип | `/dev/gpiochip0` (для Pi 5 автоматически пробует `4`) |

**Чтобы изменить пины**, Python трогать **не нужно**:

```bash
cp wiring.example.yaml wiring.yaml      # потом редактируйте wiring.yaml
# Для Docker раскомментируйте монтирование wiring.yaml в docker-compose.yml.
docker compose up -d --force-recreate
```

`wiring.yaml` позволяет переназначить любой пин, переключить active-high/low, изменить количество и частоту сирен, перекалибровать датчики — без правки кода.

---

## Дашборд

![Статус дашборда](../assets/dashboard_status.png)

Пять вкладок: **Overview** (живая влажность и управление насосами), **Cameras** (MJPEG-стримы), **FLORA** (ИИ-чат), **Events** (журнал тревог), **Settings** (уведомления и сирена).

---

## ИИ-ассистент FLORA

![Превью FLORA](../assets/FLORA_preview.jpeg)

FLORA понимает команды на естественном языке:

- *«Полей растение A»* → запускает импульсный полив
- *«Какая влажность у всех растений?»* → читает все датчики
- *«Останови насос C»* → останавливает насос C
- *«Обнаружены ли болезни?»* → проверяет последний скан FarmMonitor

Без API-ключей FLORA остаётся работоспособной офлайн через маршрутизацию по ключевым словам.

### Архитектура

| Слой | Роль |
|------|------|
| ![Layer 1](../assets/FLORA_first_layer_Architecture.png) | Маршрутизация провайдеров + fallback |
| ![Layer 2](../assets/FLORA_Second_layer_Architecture.png) | Диспетчер инструментов (датчики, насосы, камера, планировщик) |
| ![Layer 3](../assets/FLORA_Third_Lasyer_Architecture.png) | Рассуждение и интеграция FLORA |

---

## FarmMonitor

![Архитектура FarmMonitor](../assets/Farm_Monitor_Core_Architecture.png)

По расписанию сканирует всё поле. Берёт пачку кадров, отбрасывает размытые, затем запускает детекторы болезней и зрелости.

![Результат FarmMonitor](../assets/Farm_Monitor_Result.png)

Результаты сохраняются в `runtime/farmmonitor/` как JSON + JPEG. Если найдена болезнь и настроен SMTP — отправляется e-mail.

---

## Камера безопасности

![Результат камеры безопасности](../assets/Security_camera_result.png)

Инференс через кадр (frame-skip) и allow-list классов держат CPU в норме. При обнаружении угрозы сирена включается на 8 секунд и сохраняется снимок.

---

## Мост Meshtastic LoRa

![Meshtastic](../assets/MEshtastic.png)

В `.env` поставьте `MESH_ENABLED=true` и укажите `MESH_HOST` для своего узла. FLORA слушает любые каналы и ЛС, отвечает только отправителю — полностью офлайн.

---

## Хранилище

![Storage](../assets/Storage_Data_screenshot.png)

Все снятые кадры, сканы поля и снимки камеры безопасности доступны через вкладку Events в дашборде и через storage API.

---

## Опции камеры

```bash
# CSI-камера Raspberry Pi (через --input)
python plantwatch.py --input csi:0

# USB-камера
python plantwatch.py --input /dev/video0

# Сетевая / RTSP-камера
python plantwatch.py --input rtsp://user:pass@192.168.1.10/live
```

В Docker раскомментируйте соответствующую строку `command:` в `docker-compose.yml`.

---

## 🧠 Подключите свои ML-модели

Детекторы болезней и зрелости — это просто **файлы Ultralytics YOLO `.pt`**.
Обучите их на своей культуре, положите в `models/` рядом с `plantwatch.py`, и приложение их подхватит.

```bash
# Стандартные модели лежат в рабочей папке FarmMonitor.
# Замените их своими, и со следующего скана будут использоваться:
cp my_strawberry_disease.pt   FarmMonitor_Work/Disease_detect.pt
cp my_tomato_ripeness.pt      FarmMonitor_Work/Ripeness_detect.pt
```

Для **камеры безопасности** установите `PLANTWATCH_SECURITY_HEF` в `.env`, чтобы указать на свой `.hef` (Hailo); иначе используется CPU YOLO по умолчанию.

Поставляемые модели для клубники — это лишь стартовая точка, не жёсткое требование.

---

## Hailo (опционально)

```bash
# Сначала установите HailoRT SDK, затем запустите с Hailo-флагами:
python plantwatch.py --input /dev/video0 --arch hailo10h --use-frame
```

---

## CLI-справка

```
python plantwatch.py [options]

  --input             вход камеры (csi:N | /dev/videoN | rtsp://... | path)
  --arch              hailo10h | cpu (по умолчанию: cpu)
  --use-frame         использовать callback по кадрам Hailo
  --use-rpicam        использовать путь захвата picamera2 (libcamera)
```

Остальные параметры (порт, JPEG-качество, FPS, путь к HEF) — переменные окружения, см. `.env.example`.

---

## Структура проекта

```
AIgriculture/
├── plantwatch.py                       # основное приложение: дашборд + датчики + полив
├── dashboard_sample.html               # дашборд (одностраничное приложение)
├── login.html                          # экран входа
├── farm_monitor_designer_email.py      # шаблон писем с уведомлениями
├── farm_monitor_pt_scan.py             # сканер болезней / зрелости
├── farm_monitor_disease_labels.json    # YOLO-метки болезней
├── farm_monitor_ripeness_labels.json   # YOLO-метки зрелости
├── flora_agent.py / flora_config.py    # ИИ-ассистент FLORA
├── flora_report.py / flora_scheduler.py / flora_tools.py
├── meshtastic_flora_bridge.py          # мост LoRa
├── ../assets/                        # изображения, используемые в README
├── .env.example                        # ← скопировать в .env и отредактировать
├── config.example.yaml                 # ← скопировать в config.yaml (для e-mail)
├── wiring.example.yaml                 # ← скопировать в wiring.yaml (для своих пинов)
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## Лицензия

MIT — см. [LICENSE](LICENSE).
