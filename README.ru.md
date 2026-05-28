<div align="center">

# 🌱 AIgriculture

**Система умной фермы с открытым исходным кодом для Raspberry Pi**
Мониторинг влажности почвы, автоматический полив, обнаружение болезней и чат с ИИ — всё в одной веб-панели.

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

![Вид фермы](docs/assets/big_farm.jpeg)

---

## Возможности

| Подсистема | Описание |
|-----------|----------|
| **Полив** | Импульсный полив для 8 растений — включение при 45%, отключение при 65%, жёсткая блокировка при 70% |
| **FarmMonitor** | Периодическое сканирование YOLO — 5 типов болезней и 5 стадий зрелости; email-уведомления |
| **Камера безопасности** | Обнаружение людей/животных в реальном времени, двойная сирена, MJPEG-поток |
| **ИИ-ассистент FLORA** | Чат на базе Groq / Cerebras / Mistral / Gemini с управлением фермой; работает офлайн |
| **Meshtastic** | LoRa-мост — FLORA отвечает на любой канал или личное сообщение в mesh-сети |
| **Панель управления** | Одностраничное приложение с тёмной темой (обзор, камеры, ИИ, события, настройки) |

---

## Оборудование

![Прототип](docs/assets/small_prototype.jpeg)

| Компонент | Описание |
|----------|----------|
| Raspberry Pi 4/5 | 2 ГБ+ RAM, 64-bit OS Bookworm |
| ADS1115 × 2 | ADC по I2C (0x48, 0x49) — 8 каналов влажности |
| 8-канальная плата реле | Активный LOW, BCM 17 27 22 23 5 6 13 19 |
| Зуммер × 2 | BCM 18, 12 (2700 Гц) |
| Pi Camera × 2 | CSI — безопасность (csi:0) + FarmMonitor (csi:1) |
| *(опционально)* Hailo-8 M.2 | Аппаратное ускорение ИИ |

Полная схема подключения — в файле [`aigriculture.txt`](aigriculture.txt).

---

## 🚀 Быстрый старт

```bash
git clone https://github.com/darkphantom-gamer/AIgriculture.git
cd AIgriculture
cp .env.example .env   # затем отредактируйте .env (см. ниже)
docker compose up -d
```

Откройте `http://<ip-pi>:8000` в браузере.

> Нет Pi? Не проблема. GPIO и I2C автоматически отключаются — на ноутбуке работают дашборд, чат с ИИ и USB/сетевые камеры.

Нативная установка, systemd и Hailo — в [docs/SETUP.md](docs/SETUP.md).

---

## 🔑 Обязательно подставьте свои учётные данные

**В этом репозитории нет настоящих API-ключей, паролей или email — это специально.**
После `cp .env.example .env` откройте `.env` и заполните своими значениями:

| Поле в `.env` | Что вписать | Где взять |
|--------------|-------------|-----------|
| `ADMIN_USER` | Имя пользователя дашборда | (выбираете вы) |
| `ADMIN_PASS` | Надёжный пароль | (выбираете вы) — если оставить пустым, при первом запуске сгенерируется случайный |
| `GROQ_API_KEY` | Ключ Groq (рекомендуется, бесплатно, быстро) | https://console.groq.com |
| `CEREBRAS_API_KEY` | Ключ Cerebras (необязательно) | https://cloud.cerebras.ai |
| `MISTRAL_API_KEY` | Ключ Mistral (необязательно) | https://console.mistral.ai |
| `GEMINI_API_KEY` | Ключ Google AI Studio (необязательно) | https://aistudio.google.com |

Установите **хотя бы один** ИИ-провайдер — и FLORA получает полный чат с инструментами. Без ключей FLORA работает офлайн на ключевых словах.

**Email-уведомления** (тревоги FarmMonitor / отчёты FLORA):
```bash
cp config.example.yaml config.yaml      # затем отредактируйте
```

В `config.yaml` укажите свои SMTP-данные — Gmail (с **паролем приложения**), Hostinger, корпоративная почта:

```yaml
smtp:
  host: smtp.gmail.com
  port: 587
  email: you@your-domain.com
  password: your-app-password   # НЕ обычный пароль, а пароль приложения
  from_email: you@your-domain.com
notifications:
  to_email: alerts@your-domain.com
```

> **Совет по Gmail:** включите 2-факторку, затем создайте App Password на https://myaccount.google.com/apppasswords.

`.env` и `config.yaml` в `.gitignore` — настоящие секреты никогда не попадут в репозиторий.

---

## 🔌 Подключение (правьте один файл)

Стандартные пины:

| Компонент | По умолчанию BCM |
|-----------|------|
| 8 реле насосов (A → H) | `17, 27, 22, 23, 5, 6, 13, 19` (Active LOW) |
| 2 зуммера | `18, 12` (2700 Гц) |
| Датчики влажности | ADS1115 × 2 по `0x48` и `0x49` |

**Чтобы поменять пины, Python трогать не нужно:**

```bash
cp wiring.example.yaml wiring.yaml      # отредактируйте
docker compose up -d --force-recreate
```

---

## Панель управления

![Панель](docs/assets/dashboard_status.png)

Пять вкладок: **Обзор** (влажность + управление насосами), **Камеры** (MJPEG-потоки), **FLORA** (ИИ-чат), **События** (журнал уведомлений), **Настройки** (почта + сирена).

---

## ИИ-ассистент FLORA

![FLORA](docs/assets/FLORA_preview.jpeg)

FLORA понимает команды на естественном языке:

- *«Полей растение A»* → запускает импульсный полив
- *«Какая влажность у всех растений?»* → считывает все датчики
- *«Есть ли обнаруженные болезни?»* → проверяет последнее сканирование

Без ключей API FLORA работает офлайн на основе ключевых слов.

---

## FarmMonitor

![Архитектура](docs/assets/Farm_Monitor_Core_Architecture.png)

Запускает плановые сканирования поля, отфильтровывает размытые кадры, определяет болезни и стадию зрелости.

![Результат](docs/assets/Farm_Monitor_Result.png)

Результаты сохраняются в `runtime/farmmonitor/` как JSON + JPEG.

---

## Камера безопасности

![Безопасность](docs/assets/Security_camera_result.png)

Пропуск кадров и фильтр классов снижают нагрузку на CPU. При обнаружении угрозы сирена активируется на 8 секунд, снимок сохраняется.

---

## Параметры камеры

```bash
# CSI-камера Pi
python -m aigriculture --security-camera csi:0 --farm-camera csi:1

# USB-камера
python -m aigriculture --security-camera /dev/video0

# Сетевая RTSP-камера
python -m aigriculture --security-camera rtsp://192.168.1.10/live
```

---

## Лицензия

MIT — см. [LICENSE](LICENSE).
