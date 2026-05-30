<div align="center">

#  AIgriculture

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

</div>

---

![Обзор фермы](../assets/small_prototype.jpeg)

---

## Что это умеет

| Подсистема | Что вы получаете |
|------------|-------------------|
| **Полив** | Импульсный полив на столько растений, сколько вам нужно, в автоматическом режиме (запуск при 45 %, остановка при 65 %, жёсткая блокировка при 70 %) |
| **FarmMonitor** | Периодический YOLO-скан: болезни (5 классов) и стадии созревания (5 стадий), e-mail при обнаружении |
| **Камера безопасности** | Обнаружение людей/животных в реальном времени, двойная сирена, MJPEG-стрим в дашборде |
| **FLORA AI** | Мульти-провайдерный чат-ассистент (Groq / Cerebras / Mistral / Gemini), вызов инструментов фермы, офлайн-режим |
| **Meshtastic** | LoRa-мост — FLORA отвечает в любом канале или ЛС вашей mesh-сети |
| **Дашборд** | Одностраничное приложение в тёмной теме: обзор, камеры, ИИ-чат, журнал событий, настройки |

В репозитории **две точки входа** — выбирайте по своему железу:

| Скрипт | Когда брать | Движок камеры безопасности |
|--------|-------------|----------------------------|
| **`python main.py`** | По умолчанию. Работает на любом Raspberry Pi (4 / 5) или ноутбуке. | Ultralytics YOLOv8s на CPU с frame-skip — лучше распознаёт человека / медведя / корову / слона, чем nano, и работает в реальном времени на Pi 5. |
| **`python main-hailo.py`** | Когда установлен Hailo-10H AI HAT. | Hailo HEF-пайплайн — ~10× быстрее инференс. |

Всё остальное (дашборд, логин, FLORA, FarmMonitor, полив, e-mail алерты, хранилище, Meshtastic) **идентично** между скриптами. Разница только в движке инференса камеры безопасности.

---

## 🛠️ Железо — сборка для новичков / для теста

Нет настоящей фермы? **Не нужна.** Вот минимальный набор, который превращает AIgriculture в работающий настольный прототип. Каждая строка ниже — это понятная новичку замена для полноразмерной сборки.

| # | Компонент | Зачем нужно | Совет новичку |
|---|-----------|-------------|----------------|
| 1 | **Raspberry Pi 4 / 5** (4 ГБ+, рекомендуется 8 ГБ)<br><img src="../assets/hardware/Raspberrypi_5.png" width="240"> | На нём работает всё — дашборд, ИИ, логика полива. | Pi 5 быстрее, но Pi 4 (2 ГБ) тоже подойдёт. Прошейте **Raspberry Pi OS Bookworm 64-bit**. |
| 2 | **ADS1115 16-битный I²C АЦП**<br><img src="../assets/hardware/adc_module.png" width="240"> | У Pi нет аналоговых входов, а ёмкостные датчики аналоговые — АЦП переводит их в числа. | Один ADS1115 = 4 датчика. Добавляйте сколько нужно — до **четырёх** (`0x48`-`0x4B`) для 16 растений, или ещё больше шин для большей фермы. |
| 3 | **Ёмкостный датчик влажности почвы**<br><img src="../assets/hardware/moisture_sensor.png" width="240"> | Измеряет влажность почвы — это вход автоматического полива. | Только **ёмкостный** (жёлтая плата), дешёвые резистивные коррозируют за пару недель. По одному на растение. |
| 4 | **плата реле** (active-LOW, оптоизолированная)<br><img src="../assets/hardware/relay_module.png" width="240"> | Позволяет Pi включать/выключать насосы. Pi сам не может питать насос. | Берите с пометкой **5V trigger, opto-isolated**, иначе с 3,3 В Pi работать не будет. |
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
python main.py
```

Откройте `http://<pi-ip>:8000`.

> **Запускаете на ноутбуке / не на Pi?** Это тоже работает. GPIO и I2C тихо становятся «no-op», когда железа нет — вам доступны дашборд, ИИ-чат и USB / сетевые камеры.

> **Хотите нативную установку?**
> ```bash
> pip install -r requirements.txt --break-system-packages
> python main.py
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

Карта пинов по умолчанию (как поставляется в `main.py`):

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
python main.py
```

`wiring.yaml` позволяет переназначить любой пин, переключить active-high/low, изменить количество и частоту сирен, перекалибровать датчики — без правки кода.

---

## 💧 Полив

Импульсный полив, по одному насосу на растение — два способа запуска:

- **Вручную** — нажмите карточку растения на вкладке **Overview** дашборда, чтобы включить его насос по запросу.
- **Авторежим** — приложение следит за каждым датчиком влажности и поливает само: запускает импульс, когда почва опускается до **45 %**, останавливает при **65 %** и **жёстко блокирует** насос, если показание когда-либо превышает **70 %**, чтобы залипший датчик не залил растение.

Каждое растение сопоставлено одному каналу реле и одному датчику влажности (см. раздел **Подключение** выше). Насосы переключаются через оптоизолированную плату реле — Pi управляет только реле, а ток насоса через него не идёт. Начните с одного растения и расширяйте ферму на лету с помощью **«+ Add sensors»** ниже; FLORA тоже может полить, остановить и запланировать любое растение по имени.

---

## Дашборд

![Статус дашборда](../assets/dashboard_status.png)

Пять вкладок: **Overview** (живая влажность и управление насосами), **Cameras** (MJPEG-стримы), **FLORA** (ИИ-чат), **Events** (журнал тревог), **Settings** (уведомления и сирена).

---

## Камера безопасности

![Результат камеры безопасности](../assets/Security_camera_result.png)

Инференс через кадр (frame-skip) и allow-list классов держат CPU в норме. При обнаружении угрозы сирена включается на 8 секунд и сохраняется снимок.

---

## FarmMonitor

![Архитектура FarmMonitor](../assets/Farm_Monitor_Core_Architecture.png)

По расписанию сканирует всё поле. Берёт пачку кадров, отбрасывает размытые, затем запускает детекторы болезней и зрелости.

![Результат FarmMonitor](../assets/Farm_Monitor_Result.png)

![Болезнь обнаружена — живой скан](../assets/disease_detected.jpg)

*Реальный скан FarmMonitor обнаружил **Anthracnose Fruit Rot (антракнозную гниль плодов)** с уверенностью 0.87 — больная клубника распознана в реальном времени, записана в дашборд и отправлена как e-mail-уведомление.*

Результаты сохраняются в `runtime/farmmonitor/` как JSON + JPEG. Если найдена болезнь и настроен SMTP — отправляется e-mail.

---

## Хранилище

![Storage](../assets/Storage_Data_screenshot.png)

Все снятые кадры, сканы поля и снимки камеры безопасности доступны через вкладку Events в дашборде и через storage API.

---

## ➕ Добавление сенсоров на лету

В правом верхнем углу дашборда (только для администратора) есть кнопка **«+ Add sensors»**. По клику приложение:

1. Сканирует I²C-шину по всем 4 адресам ADS1115 (`0x48`-`0x4B`) × 4 канала
2. Находит каналы с правдоподобным значением влажности, ещё не занятые
3. Регистрирует их как новые растения (буквы `i`-`p`, максимум 16) и сохраняет в `.plants.json`
4. Сразу начинает опрос — без перезапуска и правки кода

Удобно, когда стартуешь со сборки на 2 сенсора и расширяешь позже.

---

## Опции камеры

**Камера безопасности** и **камера FarmMonitor** (сканы болезней / зрелости) принимают одни и те же форматы источника: RPi CSI, USB, RTSP IP или HTTP-MJPEG.

| Камера | CLI-флаг | Переменная окружения |
|--------|---------|----------------------|
| Безопасность (вторжение) | `--security-cam <SRC>` | `SECURITY_CAMERA_SOURCE` |
| FarmMonitor (болезни/зрелость) | `--farm-cam <SRC>` | `FARM_MONITOR_CAMERA` |
| RPi CSI (только для FarmMonitor) | `--use-rpicam` | — |

```bash
# CSI-камера Raspberry Pi (безопасность)
python main.py --security-cam rpi

# CSI-камера Raspberry Pi (FarmMonitor — путь picamera2)
python main.py --use-rpicam

# CSI-камера Raspberry Pi (FarmMonitor — путь OpenCV)
python main.py --farm-cam rpi

# Две USB-камеры
python main.py --security-cam /dev/video0 --farm-cam /dev/video1

# IP / RTSP-камера (работает в обоих режимах)
python main.py --security-cam rtsp://user:pass@192.168.1.10/live
python main.py --farm-cam   rtsp://user:pass@192.168.1.10/live

# HTTP-MJPEG IP-камера (один и тот же URL для обеих камер — можно тестировать без железа)
python main.py --security-cam http://camera.example/cam.cgi \
               --farm-cam   http://camera.example/cam.cgi
```

Оба флага принимают: `rpi` / `csi` (RPi CSI), `/dev/videoN` (USB), целое число (индекс камеры), `rtsp://…` (IP RTSP), `http://…` (IP MJPEG). Менять код не нужно — достаточно сменить флаг.

Можно запускать вообще без камеры — для тестирования дашборда, FLORA, логики полива и расширения сенсоров:

```bash
python main.py            # камера безопасности выключена; FarmMonitor залогирует "no camera"
```

---

## 🧠 Подключите свои ML-модели (любая культура, не только клубника)

AIgriculture не привязан к одной культуре. Помидоры, манго, перец, салат, виноград — обучите YOLOv8 на том, что выращиваете, положите веса в `Models/`, укажите переменную окружения. Без правки кода.

```bash
# 1. Положите свои обученные веса в Models/
cp my_tomato_disease.pt    Models/Tomato_disease.pt
cp my_tomato_ripeness.pt   Models/Tomato_ripeness.pt

# 2. Скажите AIgriculture использовать их (в .env или inline)
DISEASE_MODEL_PATH=Models/Tomato_disease.pt \
RIPENESS_MODEL_PATH=Models/Tomato_ripeness.pt \
python main.py
```

Для имён классов и цветов отображения скопируйте JSON-метки:

```bash
cp farm_monitor_disease_labels.json    farm_monitor_tomato_disease_labels.json
cp farm_monitor_ripeness_labels.json   farm_monitor_tomato_ripeness_labels.json
# Отредактируйте JSON под имена классов вашей модели и укажите путь:
DISEASE_LABELS_PATH=farm_monitor_tomato_disease_labels.json \
RIPENESS_LABELS_PATH=farm_monitor_tomato_ripeness_labels.json \
python main.py
```

**Камера безопасности** — в CPU-сборке принимает любой Ultralytics-совместимый вес (`SECURITY_MODEL=Models/yolov8m.pt` и т.п.). В Hailo-сборке (`main-hailo.py`) — модель `.hef`, путь задаётся через `PLANTWATCH_SECURITY_HEF`, указывающую на файл в `Models/`.

Поставляемые `Disease_detect.pt` и `Ripeness_detect.pt` настроены на клубнику — это стартовая точка, не жёсткое требование.

---

## Hailo (опциональный ускоритель)

CPU-путь по умолчанию (`main.py`) работает на любом Pi 4 / 5. Если у вас **Hailo-10H AI HAT**, сначала установите HailoRT и Hailo Apps на хост, затем запустите Hailo-сборку:

```bash
python main-hailo.py --security-cam /dev/video0
```

`main-hailo.py` и `main.py` имеют 100% общий код — дашборд, логин, FLORA, FarmMonitor, полив, Meshtastic, хранилище, e-mail-алерты. Единственное отличие — инференс камеры безопасности идёт на Hailo HEF вместо CPU YOLO (обычно в ~10 раз быстрее).

---

## CLI-справка

```
python main.py [options]            # CPU-сборка (по умолчанию)
python main-hailo.py [options]      # Hailo HAT-сборка

  --security-cam SRC  камера для обнаружения вторжений
                      rpi | csi | /dev/videoN | <индекс> | rtsp://… | http://…
  --farm-cam     SRC  камера FarmMonitor (сканы болезней / зрелости)
                      rpi | csi | /dev/videoN | <индекс> | rtsp://… | http://…
  --use-rpicam        путь захвата picamera2 (libcamera) для FarmMonitor
```

Переменные окружения (см. `.env.example`): `SECURITY_FRAME_SKIP`, `SECURITY_IMGSZ`, `SECURITY_MODEL`, `FARM_MONITOR_CAMERA`, `DISEASE_MODEL_PATH`, `RIPENESS_MODEL_PATH`, `DISEASE_LABELS_PATH`, `RIPENESS_LABELS_PATH`, `PLANTWATCH_SECURITY_HEF` (Hailo).

---

## ИИ-ассистент FLORA
*Farm Live Operation and Reasoning Assistant (Ассистент по живой операции и анализу фермы)*

![Превью FLORA](../assets/FLORA_preview.jpeg)

FLORA — это вкладка чата в дашборде, но она не только отвечает: она реально действует на ферме. Понимает команды на естественном языке:

- *«Полей растение A»* → запускает импульсный полив
- *«Какая влажность у всех растений?»* → читает все датчики
- *«Останови насос C»* → останавливает насос C
- *«Обнаружены ли болезни?»* → проверяет последний скан FarmMonitor

Каждая возможность ниже привязана к настоящему инструменту, который трогает датчики, реле, камеры, базу событий или очередь e-mail. Когда облачная LLM недоступна, FLORA переходит на детерминированную маршрутизацию по ключевым словам — все возможности продолжают работать офлайн.

### Возможности

| Возможность | Что делает |
|-------------|------------|
| **Полный анализ фермы** | Живая влажность, состояние насоса, здоровье датчиков, состояние камеры безопасности и отчёт камеры FarmMonitor по каждому активному растению — по запросу. |
| **История** | *«Что было на прошлой неделе?»*, *«покажи детекции болезней за последние 3 дня»* — отвечает из базы событий, пока события хранятся. |
| **Управление поливом** | Включить / выключить полив каждого растения индивидуально — *«полей plant C»*, *«выключи pump B»*. |
| **Управление охраной** | Включить / выключить камеру безопасности и двойную сирену — *«guard on»*, *«я ухожу»*, *«я вернулся»*. |
| **Сканы FarmMonitor** | Запуск сканов здоровья растений и готовности к сбору — *«сканируй сейчас»*, *«проверь клубнику»*. |
| **E-mail** | Отправка фото детекций, результатов сканов или вложений с отчётами на настроенный адрес оператора. |
| **PDF-отчёты** | Генерация скачиваемого PDF состояния фермы и (опционально) отправка по e-mail в том же вызове. |
| **Расписание** | Любая из перечисленных операций — на потом: *«полей plant A через 2 часа»*, *«сканируй каждое утро в 6»*. |
| **Облако или офлайн** | Облачный режим использует один из Groq / Cerebras / Mistral / Gemini для понимания естественного языка. Офлайн-режим — детерминированная маршрутизация по ключевым словам, все возможности выше остаются доступны. |

### Архитектура

FLORA работает в трёх взаимодействующих слоях:

| Слой | Роль |
|------|------|
| ![Layer 1](../assets/FLORA_first_layer_Architecture.png) | Маршрутизация провайдеров + fallback |
| ![Layer 2](../assets/FLORA_Second_layer_Architecture.png) | Диспетчер инструментов (датчики, насосы, камера, планировщик) |
| ![Layer 3](../assets/FLORA_Third_Lasyer_Architecture.png) | Рассуждение и интеграция FLORA |

---

## 📡 Мост Meshtastic LoRa

Общайтесь с FLORA вне зоны Wi-Fi через LoRa-mesh — полностью офлайн. Поставьте `MESH_ENABLED=true` в `.env` и укажите `MESH_HOST` для своего узла; FLORA слушает любые каналы и ЛС и отвечает только отправителю.

<p align="center">
  <img src="../img/meshtastic-flora-proof.jpg" alt="Реальный LoRa-чат Meshtastic ↔ FLORA" width="520">
</p>

И `main.py`, и `main-hailo.py` запускают мост Meshtastic ↔ FLORA **в том же процессе** — отдельную службу запускать не нужно. Мост:

- Подключается к локальному `meshtasticd` по TCP (по умолчанию `localhost:4403`)
- Слушает любой канал или ЛС
- Передаёт сообщения FLORA через локальный HTTP API
- Отвечает в том же канале, откуда пришёл запрос

Если библиотека Meshtastic не установлена или соединение упало — мост пишет предупреждение и `main.py` продолжает работать, дашборд никогда не блокируется. Все ключи `MESH_*` (разрешённые ноды, режим ответа, фильтр каналов) — в `.env.example`.

### Основная архитектура

![Meshtastic](../assets/MEshtastic.png)

---

## Структура проекта

```
AIgriculture/
├── main.py                             # CPU-сборка: дашборд + датчики + полив + CPU YOLO
├── main-hailo.py                       # Hailo-сборка: то же + Hailo HEF для камеры безопасности
│
├── design/                             # ── фронтенд-страницы (тема + UI) ──
│   ├── dashboard.html                  # дашборд (одностраничное приложение)
│   └── login.html                      # экран входа
│
├── assets/                             # ── статические изображения / звуки дашборда ──
│   ├── farmer.png                      # стандартный аватар пользователя
│   ├── low-cortisol.png                # картинка карточки настроения
│   ├── test_drive_avatar.png           # демо-аватар
│   ├── agrisense-favicon.svg           # фавикон
│   └── threat.mp3                      # звук сирены
│
├── Models/                             # ── ML-веса (под любую культуру) ──
│   ├── Disease_detect.pt               # YOLOv8 для болезней (по умолчанию — клубника)
│   ├── Ripeness_detect.pt              # YOLOv8 для зрелости (по умолчанию — клубника)
│   ├── Disease_detect.hef              # Hailo HEF (для Hailo-сборки, опционально)
│   └── yolov8*.pt                      # авто-скачиваемые веса для безопасности (gitignored)
│
├── farm_monitor_designer_email.py      # шаблон писем с уведомлениями
├── farm_monitor_pt_scan.py             # сканер болезней / зрелости
├── farm_monitor_disease_labels.json    # YOLO-метки болезней
├── farm_monitor_ripeness_labels.json   # YOLO-метки зрелости
├── flora_agent.py / flora_config.py    # ИИ-ассистент FLORA
├── flora_report.py / flora_scheduler.py / flora_tools.py
├── meshtastic_flora_bridge.py          # мост LoRa
│
├── docs/assets/                        # изображения, используемые в README
├── docs/{ja,hi,ru,zh}/README.md        # переведённые README
│
├── .env.example                        # ← скопировать в .env и отредактировать
├── config.example.yaml                 # ← скопировать в config.yaml (для e-mail)
├── wiring.example.yaml                 # ← скопировать в wiring.yaml (для своих пинов)
└── requirements.txt
```

Всё в `design/`, `assets/` и `Models/` **взаимозаменяемо**. Можно переопределить пути через env-переменные или просто положить новые файлы с тем же именем.

---

## Автор

**The Great Himkamal** ([@darkphantom-gamer](https://github.com/darkphantom-gamer))
Построен и поддерживается на реальном железе — клубничная ферма на Raspberry Pi 5.
Контрибьюции, модели для разных культур и переводы приветствуются.

---

## Лицензия

MIT — см. [LICENSE](LICENSE).
