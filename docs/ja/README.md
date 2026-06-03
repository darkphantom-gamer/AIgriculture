<div align="center">

#  AIgriculture

**Raspberry Pi 用のオープンソース・スマートファーム監視システム。**
土壌湿度の監視、灌漑の自動化、病害検出、収穫適期の検出、全アラートの通知、そして FLORA AI を使った農場とのチャット — すべて一つの Web ダッシュボードから。

[![English](https://img.shields.io/badge/lang-English-blue?style=for-the-badge)](../../README.md)
[![日本語](https://img.shields.io/badge/lang-日本語-red?style=for-the-badge)](README.md)
[![हिन्दी](https://img.shields.io/badge/lang-हिन्दी-orange?style=for-the-badge)](../hi/README.md)
[![Русский](https://img.shields.io/badge/lang-Русский-green?style=for-the-badge)](../ru/README.md)
[![中文](https://img.shields.io/badge/lang-中文-red?style=for-the-badge)](../zh/README.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-Pi%20native%20(3.13)-blue.svg)](https://www.python.org/downloads/)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-4%20%7C%205-c51a4a)](https://www.raspberrypi.com/)
[![Android build](https://github.com/darkphantom-gamer/AIgriculture/actions/workflows/android.yml/badge.svg?branch=main)](https://github.com/darkphantom-gamer/AIgriculture/actions/workflows/android.yml)

</div>

---

![農場全景](../assets/small_prototype.jpeg)

---

<div align="center">

### 📱 アプリを入手 — AIgriculture Mobile <sub>(beta)</sub>

[![Click here to download APK](https://img.shields.io/badge/⬇%20CLICK%20HERE%20TO%20DOWNLOAD%20APK-AIgriculture%20Mobile%20beta-00cdb5?style=for-the-badge&logo=android&logoColor=white)](https://github.com/darkphantom-gamer/AIgriculture/releases/download/app-v0.1.0/AIgriculture.apk)

**スマートフォンからリアルタイムで農場を操作** — FLORA チャット、ライブカメラ、FarmMonitor、土壌湿度、灌漑、脅威 / スキャン / 水やり通知。

[See Releases →](https://github.com/darkphantom-gamer/AIgriculture/releases/tag/app-v0.1.0)

</div>

---

## できること

| サブシステム | 提供する機能 |
|--------------|--------------|
| **灌漑** | プラントの数に上限なしのバースト灌漑（自動モード：湿度 45 % で起動、65 % で停止、70 % でハードロック）|
| **FarmMonitor** | YOLO による定期スキャン — 病害 5 クラス・熟度 5 段階を検出し、メールで通知 |
| **セキュリティカメラ** | 人や動物のリアルタイム検出、デュアルブザーサイレン、ダッシュボードへの MJPEG ストリーム |
| **FLORA AI** | マルチプロバイダー対応のチャットアシスタント（Groq / Cerebras / Mistral / Gemini）、農場ツール呼び出し、オフラインフォールバック |
| **Meshtastic** | LoRa ブリッジ — FLORA がメッシュネットワーク上の任意のチャンネルまたは DM に応答 |
| **ダッシュボード** | ダークテーマ・シングルページアプリ：概要、カメラ、AI チャット、イベントログ、設定 |

本リポジトリは **2 つのエントリポイント** を提供します — お使いのハードウェアに合う方を選んでください:

| スクリプト | こんな時に | セキュリティカメラエンジン |
|------------|------------|----------------------------|
| **`python main.py`** | デフォルト。Raspberry Pi (4 / 5) でもラップトップでも動きます。 | Ultralytics YOLOv8s を CPU + フレームスキップで実行 — nano より人 / 熊 / 牛 / 象の検出率が高く、Pi 5 でリアルタイム。 |
| **`python main-hailo.py`** | Hailo-10H AI HAT を装着している場合。 | Hailo HEF パイプライン — 約 10 倍高速。 |

それ以外（ダッシュボード、ログイン、FLORA、FarmMonitor、灌漑、メール通知、ストレージ、Meshtastic）は両者で **完全に同じ** です。セキュリティカメラの推論エンジンだけが違います。

---

## 🛠️ ハードウェア — 初心者・お試しビルド

実際の農場がなくても **大丈夫です**。AIgriculture を卓上プロトタイプとして動かせる最小構成を以下にまとめました。初心者でも揃えやすい部品ばかりです。

| # | 部品 | なぜ必要か | 初心者へのヒント |
|---|------|-------------|-----------------|
| 1 | **Raspberry Pi 4 / 5**（4 GB 以上、8 GB 推奨）<br><img src="../assets/hardware/Raspberrypi_5.png" width="240"> | ダッシュボード、AI、灌漑ロジックなどすべてを動かします。 | Pi 5 が一番速いですが、Pi 4 (2 GB) でも試せます。**Raspberry Pi OS Bookworm 64-bit** を入れてください。 |
| 2 | **ADS1115 16 bit I²C ADC**<br><img src="../assets/hardware/adc_module.png" width="240"> | Pi にはアナログ入力がなく、容量式湿度センサーはアナログなので変換が必要です。 | ADS1115 一つで 4 センサー。必要なだけ追加 — **4 個**（`0x48`-`0x4B`）まで増やせば 16 プラント、I²C バスを増設すればさらに大規模化も可能。 |
| 3 | **容量式土壌湿度センサー**<br><img src="../assets/hardware/moisture_sensor.png" width="240"> | 土の湿り気を測ります。自動灌漑の入力になります。 | 必ず **容量式（黄色い基板）** を選んでください。安価な抵抗式は数週間で腐食します。プラントごとに 1 個。 |
| 4 | **リレーボード**（アクティブ LOW、オプトカプラ絶縁）<br><img src="../assets/hardware/relay_module.png" width="240"> | Pi がポンプを ON/OFF するために使います。Pi 自体ではポンプの電源は供給できません。 | **5V トリガ、オプトカプラ絶縁** と書かれているものを選ぶこと。そうでないと 3.3V GPIO で動作しません。 |
| 5 | **小型の 5V または 12V DC 水ポンプ**<br><img src="../assets/hardware/water_pump.png" width="240"> | 実際にプラントへ水を送る部品です。 | プラント 1 つにつき 1 個。**必ず別電源を用意してください。Pi の 5V から取らないでください。** Pi はリレーを制御するだけです。 |
| 6 | **Raspberry Pi カメラ（CSI）** または **USB Web カメラ**<br><img src="../assets/hardware/pi-camera.jpeg" width="200"> &nbsp; <img src="../assets/hardware/usb_camera.png" width="200"> | 一方は FarmMonitor の病害・熟度スキャン用、もう一方はセキュリティカメラ用です。 | カメラ 1 台でも始められます。`--security-camera` だけ指定して `--farm-camera` を省略してください。RTSP IP カメラにも対応。 |
| 7 | **ブレッドボード + ジャンパーワイヤー**<br><img src="../assets/hardware/breadboard_and_jumper_wires.png" width="240"> | はんだ付けなしで配線できます。 | センサー〜ADC は メス-メス、ADC〜Pi は オス-メス を用意するとスムーズです。 |
| **+** | **Hailo-10H AI HAT**（オプション、高速推論）<br><img src="../assets/hardware/hailo10h_optional.png" width="240"> | YOLO 推論をハードウェアで加速し、スキャン時間を大幅に短縮します。 | **初心者ビルドではスキップ。** 普通の Pi でも CPU 経路で問題なく動きます。スキャンを高速化したい場合だけ追加してください。 |
| **+** | **Meshtastic LoRa 無線機**（オプション、オフグリッド・チャット）<br><img src="../assets/hardware/LORA_chip_with_433hz_antenna.png" width="240"> | Wi-Fi 圏外でも LoRa メッシュで FLORA と話せます。 | オプション。Heltec / LilyGo ボードと 433 / 868 / 915 MHz アンテナで動作。Web UI だけで十分ならスキップで構いません。 |

**最小お試しビルド**（卓上でダッシュボードを触ってみたい人向け）:
> Pi 1 台・ADS1115 1 個・湿度センサー 1 本・USB カメラ 1 台。これだけ。リレーもポンプも Hailo も不要。ダッシュボードが立ち上がったら "+ Add sensors" ボタンで増設できます。

---

## 🚀 クイックスタート

```bash
git clone https://github.com/darkphantom-gamer/AIgriculture.git
cd AIgriculture

# 1) システムパッケージ（一回のみ）
sudo apt update
sudo apt install -y python3-lgpio python3-pip i2c-tools mariadb-server
sudo raspi-config nonint do_i2c 0          # I2C を有効にする

# 2) Python 依存関係
pip install -r requirements.txt --break-system-packages

# 3) 設定
cp .env.example .env                       # その後 .env を編集（管理者ユーザー/パスワード、API キー）
cp config.example.yaml config.yaml         # その後 config.yaml を編集（メールアラート用 SMTP）
cp wiring.example.yaml wiring.yaml         # デフォルトピンを変更した場合のみ

# 4) 実行 — エントリーポイントを 1 つ選ぶ
python main.py                              # CPU ビルド（デフォルト）
# python main-hailo.py                      # Hailo ビルド（HAT が接続されている場合のみ）

# frame-skip CPU YOLO でセキュリティカメラを有効にする:
python main.py --security-cam /dev/video0
```

ブラウザで `http://<pi-ip>:8000` を開き、`.env` に設定した `ADMIN_USER` / `ADMIN_PASS` でログインします。

> **ラップトップ／非 Pi で実行する場合？** `main.py`（CPU ビルド）を使ってください。ハードウェアが無い場合、GPIO と I²C は静かに no-op になります — フルダッシュボード、AI チャット、USB / ネットワークカメラはそのまま使えます。ステップ 1 は省略して `pip install -r requirements.txt` と `python main.py` だけで OK です。

### データベース

デフォルト設定では `localhost:3306` の MariaDB / MySQL に接続します。`sudo apt install mariadb-server` の後、`.env` に合わせてユーザーとデータベースを作成してください:

```bash
sudo mysql -e "CREATE DATABASE plantmonitor;
               CREATE USER 'plantmonitor'@'localhost' IDENTIFIED BY 'CHANGE-ME';
               GRANT ALL ON plantmonitor.* TO 'plantmonitor'@'localhost';
               FLUSH PRIVILEGES;"
```

`.env` の `DB_USER`、`DB_PASS`、`DB_NAME` を合わせてください。アプリは初回起動時に自動でテーブルを作成します。

### 起動時に実行する（オプション）

```bash
sudo tee /etc/systemd/system/aigriculture.service > /dev/null <<EOF
[Unit]
Description=AIgriculture
After=network-online.target mariadb.service
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/AIgriculture
ExecStart=/usr/bin/python3 /home/pi/AIgriculture/main.py --security-cam /dev/video0
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl enable --now aigriculture
```

---

## 🔑 自分の認証情報を必ず入れてください

**本リポジトリには実際の API キー、パスワード、メールアドレスは一切含まれていません — そういう設計です。**
`cp .env.example .env` の後、`.env` を開いて自分の情報を入力します:

| `.env` のキー | 入れるもの | 取得先 |
|---------------|------------|--------|
| `ADMIN_USER` | 使いたいダッシュボードユーザー名 |（自分で決める） |
| `ADMIN_PASS` | 強力なパスワード |（自分で決める） — 空のままにすると初回起動時にランダムなものが表示されます |
| `DB_USER` / `DB_PASS` / `DB_NAME` | MariaDB / MySQL の認証情報 |（自分で決める — データベース節を参照） |
| `GROQ_API_KEY` | Groq の API キー（推奨、高速・無料） | https://console.groq.com |
| `CEREBRAS_API_KEY` | Cerebras の API キー（任意） | https://cloud.cerebras.ai |
| `MISTRAL_API_KEY` | Mistral の API キー（任意） | https://console.mistral.ai |
| `GEMINI_API_KEY` | Google AI Studio の API キー（任意） | https://aistudio.google.com |

AI プロバイダを **どれか一つ** 設定すれば FLORA はツール呼び出し対応のフルチャットを行います。すべて空のままでも、FLORA はキーワードルーティングでオフライン動作します。

**メール通知**（FarmMonitor 病害アラート、FLORA レポート）を使う場合は:
```bash
cp config.example.yaml config.yaml      # その後 config.yaml を編集
```

`config.yaml` に自分の SMTP 情報を入れてください — Gmail（アプリパスワード）、Hostinger、学校メールなど SMTP に対応するものなら何でも:

```yaml
smtp:
  host: smtp.gmail.com          # または smtp.hostinger.com、smtp.office365.com など
  port: 587
  email: you@your-domain.com    # 自分の実際のアドレス
  password: your-app-password   # 普通のパスワードではなくアプリパスワード
  from_email: you@your-domain.com
notifications:
  to_email: alerts@your-domain.com
```

> **Gmail のヒント:** 2 段階認証を有効化してから https://myaccount.google.com/apppasswords で **アプリパスワード** を作成し、そちらを使います。通常の Gmail パスワードは SMTP で拒否されます。

`.env` と `config.yaml` はどちらも git-ignore 済みなので、実際の秘密情報はリポジトリに混入しません。

---

## 🔌 配線（1 ファイル編集すれば自分のボードに合わせられます）

デフォルトのピン割り当て（`main.py` 同梱のもの）:

| 部品 | デフォルト BCM ピン |
|------|---------------------|
| 8 ポンプリレー（プラント A → H） | `17, 27, 22, 23, 5, 6, 13, 19`（アクティブ LOW） |
| 2 ブザーサイレン | `18, 12`（2700 Hz） |
| 8 湿度センサー | ADS1115 × 2、I²C `0x48` と `0x49` |
| I²C バス | `/dev/i2c-1` |
| GPIO チップ | `/dev/gpiochip0`（失敗した時は Pi 5 向けに `4` を自動試行） |

**ピンを変更したい場合**、Python を編集する必要は **ありません**:

```bash
cp wiring.example.yaml wiring.yaml      # その後 wiring.yaml を編集
python main.py
```

`wiring.yaml` でピンの再割り当て、アクティブ HIGH/LOW の切り替え、ブザーの個数や周波数、湿度センサーのキャリブレーションをコードなしで変更できます。

---

## 💧 灌漑

バースト灌漑、プラント 1 つにつきポンプ 1 台 — 2 通りの動かし方ができます:

- **手動** — ダッシュボードの **Overview** タブでプラントのカードをタップすると、そのポンプをその場で作動させます。
- **自動モード** — アプリが各湿度センサーを監視し、自分で水やりします。土壌が **45 %** まで下がるとバーストを開始、**65 %** で停止、読み取り値が **70 %** を超えたらポンプを **ハードロック** します — センサーが固着しても水浸しにならないようにするためです。

各プラントは 1 つのリレーチャンネルと 1 つの湿度センサーに対応します（上の **配線** 節を参照）。ポンプはオプトカプラ絶縁のリレーボード経由で ON/OFF され、Pi はリレーを駆動するだけでポンプ電流は流しません。プラント 1 つから始め、下の **「+ Add sensors」** でランタイムに農場を拡張できます。FLORA も名前を指定して任意のプラントに水やり・停止・スケジュールができます。

---

## ダッシュボード

![ダッシュボード ステータス](../assets/dashboard_status.png)

5 つのタブ: **Overview**（リアルタイム湿度・ポンプ制御）、**Cameras**（MJPEG ストリーム）、**FLORA**（AI チャット）、**Events**（アラートログ）、**Settings**（通知・サイレン）。

---

## セキュリティカメラ

![セキュリティカメラ結果](../assets/Security_camera_result.png)

フレームスキップ推論（N フレーム毎）とクラス許可リストで CPU 負荷を抑えます。脅威検出時はサイレンが 8 秒作動し、スナップショットを保存します。

---

## FarmMonitor

![FarmMonitor アーキテクチャ](../assets/Farm_Monitor_Core_Architecture.png)

スケジュールに従って圃場全体をスキャンします。フレームのバッチをキャプチャし、ブレた画像を除去してから病害・熟度検出を実行します。

![FarmMonitor 結果](../assets/Farm_Monitor_Result.png)

![病害を検出 — ライブスキャン](../assets/disease_detected.jpg)

*実際の FarmMonitor スキャンが **Anthracnose Fruit Rot（炭疽病による果実腐敗）** を信頼度 0.87 で検出 — 病気のイチゴをリアルタイムで捉え、ダッシュボードに記録し、メールアラートとして送信します。*

結果は `runtime/farmmonitor/` に JSON + JPEG として保存されます。病害が検出されて SMTP が設定されていれば、メールでアラートを送信します。

---

## ストレージ

![Storage](../assets/Storage_Data_screenshot.png)

キャプチャしたフレーム、農場スキャン、セキュリティ・スナップショットは、ダッシュボードの Events タブとストレージ API から閲覧できます。

---

## ➕ センサーをランタイムで追加

ダッシュボードの右上（管理者専用）に **「+ Add sensors」** ボタンがあります。クリックすると:

1. すべての ADS1115 アドレス（`0x48`-`0x4B`）× 各 4 チャンネルをスキャン
2. 妥当な湿度値を返し、まだ使われていないチャンネルを発見
3. 新しいプラント（`i`-`p` まで、最大 16）として登録し `.plants.json` に永続化
4. すぐにポーリングを開始 — 再起動・コード編集不要

2 センサーのお試しビルドから始めて、後で増やしたい場合に便利です。

---

## カメラ設定

**セキュリティカメラ** と **FarmMonitor カメラ** (病害 / 熟度スキャン) は同じソース形式を受け付けます: RPi CSI、USB、RTSP IP、HTTP-MJPEG。ソースはカメラごとに CLI フラグまたは環境変数で選択します。

| カメラ | CLI フラグ | 環境変数 |
|--------|-----------|---------|
| セキュリティ (侵入検知) | `--security-cam <SRC>` | `SECURITY_CAMERA_SOURCE` |
| FarmMonitor (病害/熟度) | `--farm-cam <SRC>` | `FARM_MONITOR_CAMERA` |
| RPi CSI (FarmMonitor 専用ショートカット) | `--use-rpicam` | — |

```bash
# Raspberry Pi CSI カメラ（セキュリティ）
python main.py --security-cam rpi

# Raspberry Pi CSI カメラ（FarmMonitor — picamera2 経路）
python main.py --use-rpicam

# Raspberry Pi CSI カメラ（FarmMonitor — OpenCV 経路）
python main.py --farm-cam rpi

# 2 つの USB カメラ
python main.py --security-cam /dev/video0 --farm-cam /dev/video1

# IP / RTSP カメラ（どちらにも使える）
python main.py --security-cam rtsp://user:pass@192.168.1.10/live
python main.py --farm-cam   rtsp://user:pass@192.168.1.10/live

# HTTP-MJPEG IP カメラ（同じ URL を両方のカメラに使えるのでハードウェア無しでもテスト可能）
python main.py --security-cam http://camera.example/cam.cgi \
               --farm-cam   http://camera.example/cam.cgi

# 混在も可能: USB セキュリティカメラ + IP FarmMonitor カメラ（例: 温室カメラ）
python main.py --security-cam /dev/video0 \
               --farm-cam   rtsp://greenhouse:5554/live
```

両方のフラグが受け付ける形式: `rpi` / `csi`（OpenCV 経由の RPi CSI）、`/dev/videoN`（USB）、整数（カメラ インデックス）、`rtsp://…`（IP RTSP）、`http://…`（IP MJPEG）。コード編集は不要 — フラグを変えるだけです。

カメラ無しでもダッシュボード、FLORA、灌漑ロジック、センサー拡張をテストできます:

```bash
python main.py            # セキュリティカメラ無効; FarmMonitor は "no camera" を記録
```

---

## 🧠 自分の ML モデルを差し込む (イチゴ以外の任意の作物に)

AIgriculture は作物にとらわれません。トマト、マンゴー、ピーマン、レタス、ブドウ — 育てているものに YOLOv8 を学習させ、重みを `Models/` に入れて、環境変数で指定するだけ。コード編集は不要です。

```bash
# 1. 自前の学習済み重みを Models/ に入れる
cp my_tomato_disease.pt    Models/Tomato_disease.pt
cp my_tomato_ripeness.pt   Models/Tomato_ripeness.pt

# 2. AIgriculture に使うように伝える（.env でも、インラインでも）
DISEASE_MODEL_PATH=Models/Tomato_disease.pt \
RIPENESS_MODEL_PATH=Models/Tomato_ripeness.pt \
python main.py
```

クラス名と表示色は、同梱のラベル JSON を複製してカスタマイズします:

```bash
cp farm_monitor_disease_labels.json    farm_monitor_tomato_disease_labels.json
cp farm_monitor_ripeness_labels.json   farm_monitor_tomato_ripeness_labels.json
# モデルのクラス名に合わせて JSON を編集し、env で指定:
DISEASE_LABELS_PATH=farm_monitor_tomato_disease_labels.json \
RIPENESS_LABELS_PATH=farm_monitor_tomato_ripeness_labels.json \
python main.py
```

**セキュリティカメラ** は、CPU ビルドでは任意の Ultralytics 互換重み（`SECURITY_MODEL=Models/yolov8m.pt` など）。Hailo ビルド（`main-hailo.py`）は `.hef` モデル — `PLANTWATCH_SECURITY_HEF` を `Models/` 内のファイルに向けます。

同梱の `Disease_detect.pt` と `Ripeness_detect.pt` はイチゴ向けにチューニングされています — 出発点であり、必須ではありません。

---

## Hailo（オプションのアクセラレータ）

デフォルトの CPU 経路（`main.py`）はどの Pi 4 / 5 でも動作します。**Hailo-10H AI HAT** があれば、ホストに HailoRT と Hailo Apps をインストールしてから Hailo ビルドを起動:

```bash
python main-hailo.py --security-cam /dev/video0
```

`main-hailo.py` と `main.py` のダッシュボード、ログイン、FLORA、FarmMonitor、灌漑、Meshtastic、ストレージ、メールアラートのコードは 100% 共通です。違いはセキュリティカメラ推論が CPU YOLO か Hailo HEF かだけ — 通常 ~10× 高速です。

HAT が実際には接続されていない場合、`main-hailo.py` は警告をログに出力し、それ以外はすべて動作し続けます。設定ファイルやデータベースに触れることなく、いつでも 2 つのスクリプトを切り替えられます。

---

## CLI リファレンス

```
python main.py [options]            # CPU ビルド (デフォルト)
python main-hailo.py [options]      # Hailo HAT ビルド

  --security-cam SRC  侵入検知用カメラ
                      rpi | csi | /dev/videoN | <index> | rtsp://… | http://…
  --farm-cam     SRC  FarmMonitor 用カメラ（病害 / 熟度スキャン）
                      rpi | csi | /dev/videoN | <index> | rtsp://… | http://…
  --use-rpicam        FarmMonitor の picamera2 (libcamera) キャプチャ経路
```

環境変数 (`.env.example` 参照):
- `SECURITY_FRAME_SKIP` (デフォルト 5)、`SECURITY_IMGSZ` (デフォルト 640)、
  `SECURITY_MODEL` (デフォルト `yolov8s.pt` — 最大 FPS は `yolov8n.pt`、
  より高い recall は `yolov8m.pt`)。
- `FARM_MONITOR_CAMERA` — `/dev/videoN`、`rpi`、`rtsp://…`、`http://…`、または
  USB カメラの自動検出には空白。
- `DISEASE_MODEL_PATH` / `RIPENESS_MODEL_PATH` — `Models/` 内の任意の YOLOv8 `.pt`
  を指定してコード変更なしに作物を切り替え。
- `DISEASE_LABELS_PATH` / `RIPENESS_LABELS_PATH` — カスタムラベル JSON へのパス
  (付属の `farm_monitor_*_labels.json` でフォーマット確認)。
- `PLANTWATCH_SECURITY_HEF` — Hailo ビルド用の Hailo HEF モデル。

---

## FLORA AI アシスタント
*Farm Live Operation and Reasoning Assistant（農場ライブ操作・推論アシスタント）*

![FLORA プレビュー](../assets/FLORA_preview.jpeg)

FLORA はダッシュボードのチャットタブですが、答えるだけでなく実際に農場を操作します。自然言語のコマンドを理解します:

- *「プラント A に水をやって」* → バースト灌漑を起動
- *「全プラントの湿度はどう？」* → 全センサーを読み出し
- *「C のポンプを止めて」* → ポンプ C を停止
- *「病気は検出されてる？」* → 最新の FarmMonitor スキャンを確認

下の機能はすべてセンサー・リレー・カメラ・イベントデータベース・メールキューに接続された実ツールに紐づいています。クラウド LLM が利用できないときは決定論的なキーワードルーティングにフォールバックするため、どの機能もオフラインで動き続けます。

### 機能

| 機能 | 内容 |
|------|------|
| **農場フル分析** | アクティブな全プラントのライブ水分量、ポンプ状態、センサー健全性、防犯カメラ状態、FarmMonitor カメラ読み取り結果 — オンデマンドで取得。 |
| **履歴クエリ** | *「先週なにがあった？」*、*「過去3日の病害検知を見せて」* — イベントデータベースから、イベントが保持されている期間内で回答。 |
| **灌漑制御** | プラントごとに個別に灌水を開始 / 停止 — *「plant C に水やり」*、*「pump B を止めて」*。 |
| **ガード制御** | 防犯カメラ＋デュアルブザーサイレンを ON / OFF — *「guard on」*、*「出かけます」*、*「戻りました」*。 |
| **FarmMonitor スキャン** | プラントヘルスと収穫適期スキャンをオンデマンド実行 — *「今すぐスキャン」*、*「いちごを見て」*。 |
| **メール** | 検知写真、スキャン結果、レポート添付ファイルを設定済みのオペレーターアドレスに送信。 |
| **PDF レポート** | 農場状態のダウンロード可能な PDF を生成し、同じ呼び出しでメール送信も任意で実行。 |
| **スケジュール** | 上記いずれも後でスケジュール可能 — *「2 時間後に plant A へ水やり」*、*「毎朝 6 時にスキャン」*。 |
| **クラウド or オフライン** | クラウドモード：Groq / Cerebras / Mistral / Gemini のいずれか 1 つを自然言語理解に使用。オフラインモード：決定論的キーワードルーティング — 上記の全機能が動作します。 |

### アーキテクチャ

FLORA は協調する 3 層で動作します:

| レイヤ | 役割 |
|--------|------|
| ![Layer 1](../assets/FLORA_first_layer_Architecture.png) | プロバイダ ルーティング + フォールバック |
| ![Layer 2](../assets/FLORA_Second_layer_Architecture.png) | ツールディスパッチ（センサー、ポンプ、カメラ、スケジューラ） |
| ![Layer 3](../assets/FLORA_Third_Lasyer_Architecture.png) | FLORA 推論と統合 |

---

## 📡 Meshtastic LoRa ブリッジ

Wi-Fi 圏外でも LoRa メッシュで FLORA と話せます — 完全オフグリッド。`.env` で `MESH_ENABLED=true` を設定し、`MESH_HOST` を自分のノードに向けます。FLORA は任意のチャンネル / DM を待ち受け、送信元にのみ返信します。

<p align="center">
  <img src="../img/meshtastic-flora-proof.jpg" alt="Meshtastic ↔ FLORA リアル LoRa チャット" width="520">
</p>

`main.py` と `main-hailo.py` のどちらも Meshtastic ↔ FLORA ブリッジを **同じプロセス内で** 起動します — 別サービスを動かす必要はありません。このブリッジは:

- ローカル `meshtasticd` に TCP 接続（デフォルト `localhost:4403`）
- どのチャンネルでも DM でも待ち受け
- インプロセス HTTP API 経由で FLORA に転送
- 受信したチャンネルだけに返信

Meshtastic ライブラリが入っていない場合や接続が切れた場合は警告ログを出すだけで、`main.py` は止まりません — ダッシュボードを決してブロックしません。`MESH_*` の全オプション（許可ノード、返信モード、チャンネルフィルタ）は `.env.example` を参照してください。

### コアアーキテクチャ

![Meshtastic](../assets/MEshtastic.png)

---

## プロジェクト構成

```
AIgriculture/
├── main.py                             # CPU ビルド: ダッシュボード + センサー + 灌漑 + CPU YOLO
├── main-hailo.py                       # Hailo ビルド: 同上 + Hailo HEF セキュリティカメラ
│
├── design/                             # ── フロントエンドのページ (テーマ + UI) ──
│   ├── dashboard.html                  # ダッシュボード（シングルページ アプリ）
│   └── login.html                      # ログイン画面
│
├── assets/                             # ── ダッシュボードが配信する画像 / 音声 ──
│   ├── farmer.png                      # デフォルトのユーザーアバター
│   ├── low-cortisol.png                # ムードカードの画像
│   ├── test_drive_avatar.png           # デモ用アバター
│   ├── agrisense-favicon.svg           # ファビコン
│   └── threat.mp3                      # サイレン音
│
├── Models/                             # ── ML 重み (作物に応じて差し替え可能) ──
│   ├── Disease_detect.pt               # YOLOv8 病害検出 (デフォルトはイチゴ)
│   ├── Ripeness_detect.pt              # YOLOv8 熟度検出 (デフォルトはイチゴ)
│   ├── Disease_detect.hef              # Hailo HEF (Hailo ビルド用、オプション)
│   └── yolov8*.pt                      # 自動ダウンロードされるセキュリティ重み (gitignored)
│
├── farm_monitor_designer_email.py      # 通知メールのテンプレート
├── farm_monitor_pt_scan.py             # 病害・熟度の .pt スキャナ
├── farm_monitor_disease_labels.json    # 病害クラス (YOLO ラベル)
├── farm_monitor_ripeness_labels.json   # 熟度クラス (YOLO ラベル)
├── flora_agent.py / flora_config.py    # FLORA AI アシスタント
├── flora_report.py / flora_scheduler.py / flora_tools.py
├── meshtastic_flora_bridge.py          # LoRa ブリッジ
│
├── docs/assets/                        # README で使用する画像
├── docs/{ja,hi,ru,zh}/README.md        # 翻訳された READMEs
│
├── .env.example                        # ← .env にコピーして編集
├── config.example.yaml                 # ← config.yaml にコピーして編集（メール用）
├── wiring.example.yaml                 # ← wiring.yaml にコピーして編集（独自ピン用）
└── requirements.txt
```

`design/`、`assets/`、`Models/` の中身はすべて **差し替え可能** です。env 変数でパスを上書きするか、同じファイル名で新しいファイルを置くだけです。

---

## 作者

**The Great Himkamal** ([@darkphantom-gamer](https://github.com/darkphantom-gamer))
実機 — Raspberry Pi 5 で動く本物のイチゴ農場 — で構築・運用しています。
コントリビューション、作物モデル、翻訳の追加歓迎です。

---

## ライセンス

MIT — [LICENSE](LICENSE) を参照してください。
