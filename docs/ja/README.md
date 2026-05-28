<div align="center">

# 🌱 AIgriculture

**Raspberry Pi 用のオープンソース・スマートファームシステム。**
土壌湿度の監視、灌漑の自動化、病害検出、AI とのチャット — すべて一つの Web ダッシュボードから。

[![English](https://img.shields.io/badge/lang-English-blue?style=for-the-badge)](../../README.md)
[![日本語](https://img.shields.io/badge/lang-日本語-red?style=for-the-badge)](README.md)
[![हिन्दी](https://img.shields.io/badge/lang-हिन्दी-orange?style=for-the-badge)](../hi/README.md)
[![Русский](https://img.shields.io/badge/lang-Русский-green?style=for-the-badge)](../ru/README.md)
[![中文](https://img.shields.io/badge/lang-中文-red?style=for-the-badge)](../zh/README.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-Pi%20native%20(3.13)-blue.svg)](https://www.python.org/downloads/)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-4%20%7C%205-c51a4a)](https://www.raspberrypi.com/)

</div>

---

![農場全景](../assets/small_prototype.jpeg)

---

## できること

| サブシステム | 提供する機能 |
|--------------|--------------|
| **灌漑** | 8 プラント・バースト灌漑（自動モード：湿度 45 % で起動、65 % で停止、70 % でハードロック）|
| **FarmMonitor** | YOLO による定期スキャン — 病害 5 クラス・熟度 5 段階を検出し、メールで通知 |
| **セキュリティカメラ** | 人や動物のリアルタイム検出、デュアルブザーサイレン、ダッシュボードへの MJPEG ストリーム |
| **FLORA AI** | マルチプロバイダー対応のチャットアシスタント（Groq / Cerebras / Mistral / Gemini）、農場ツール呼び出し、オフラインフォールバック |
| **Meshtastic** | LoRa ブリッジ — FLORA がメッシュネットワーク上の任意のチャンネルまたは DM に応答 |
| **ダッシュボード** | ダークテーマ・シングルページアプリ：概要、カメラ、AI チャット、イベントログ、設定 |

---

## 🛠️ ハードウェア — 初心者・お試しビルド

実際の農場がなくても **大丈夫です**。AIgriculture を卓上プロトタイプとして動かせる最小構成を以下にまとめました。初心者でも揃えやすい部品ばかりです。

| # | 部品 | なぜ必要か | 初心者へのヒント |
|---|------|-------------|-----------------|
| 1 | **Raspberry Pi 4 / 5**（4 GB 以上、8 GB 推奨）<br><img src="../assets/hardware/Raspberrypi_5.png" width="240"> | ダッシュボード、AI、灌漑ロジックなどすべてを動かします。 | Pi 5 が一番速いですが、Pi 4 (2 GB) でも試せます。**Raspberry Pi OS Bookworm 64-bit** を入れてください。 |
| 2 | **ADS1115 16 bit I²C ADC**<br><img src="../assets/hardware/adc_module.png" width="240"> | Pi にはアナログ入力がなく、容量式湿度センサーはアナログなので変換が必要です。 | ADS1115 一つで 4 センサー。デフォルト 8 プラント用なら **2 個**（`0x48` + `0x49`）、最大 **4 個**（`0x48`-`0x4B`）で 16 プラント。 |
| 3 | **容量式土壌湿度センサー**<br><img src="../assets/hardware/moisture_sensor.png" width="240"> | 土の湿り気を測ります。自動灌漑の入力になります。 | 必ず **容量式（黄色い基板）** を選んでください。安価な抵抗式は数週間で腐食します。プラントごとに 1 個。 |
| 4 | **8 チャンネル リレーボード**（アクティブ LOW、オプトカプラ絶縁）<br><img src="../assets/hardware/relay_module.png" width="240"> | Pi がポンプを ON/OFF するために使います。Pi 自体ではポンプの電源は供給できません。 | **5V トリガ、オプトカプラ絶縁** と書かれているものを選ぶこと。そうでないと 3.3V GPIO で動作しません。 |
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
cp .env.example .env            # その後 .env を編集（次の節を参照）
python main.py
```

ブラウザで `http://<pi-ip>:8000` を開きます。

> **ラップトップ／非 Pi で実行する場合も** これは動きます。GPIO や I2C はハードウェアが無い時は静かに no-op するので、ダッシュボード、AI チャット、(USB/ネットワーク) カメラはそのまま使えます。

> **ネイティブインストールを行う場合：**
> ```bash
> pip install -r requirements.txt --break-system-packages
> python main.py
> ```

---

## 🔑 自分の認証情報を必ず入れてください

**本リポジトリには実際の API キー、パスワード、メールアドレスは一切含まれていません — そういう設計です。**
`cp .env.example .env` の後、`.env` を開いて自分の情報を入力します:

| `.env` のキー | 入れるもの | 取得先 |
|---------------|------------|--------|
| `ADMIN_USER` | 使いたいダッシュボードユーザー名 |（自分で決める） |
| `ADMIN_PASS` | 強力なパスワード |（自分で決める）|
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

## ダッシュボード

![ダッシュボード ステータス](../assets/dashboard_status.png)

5 つのタブ: **Overview**（リアルタイム湿度・ポンプ制御）、**Cameras**（MJPEG ストリーム）、**FLORA**（AI チャット）、**Events**（アラートログ）、**Settings**（通知・サイレン）。

---

## FLORA AI アシスタント

![FLORA プレビュー](../assets/FLORA_preview.jpeg)

FLORA は自然言語のコマンドを理解します:

- *「プラント A に水をやって」* → バースト灌漑を起動
- *「全プラントの湿度はどう？」* → 全センサーを読み出し
- *「C のポンプを止めて」* → ポンプ C を停止
- *「病気は検出されてる？」* → 最新の FarmMonitor スキャンを確認

API キーが未設定でも、キーワードルーティングで完全オフライン動作します。

### アーキテクチャ

| レイヤ | 役割 |
|--------|------|
| ![Layer 1](../assets/FLORA_first_layer_Architecture.png) | プロバイダ ルーティング + フォールバック |
| ![Layer 2](../assets/FLORA_Second_layer_Architecture.png) | ツールディスパッチ（センサー、ポンプ、カメラ、スケジューラ） |
| ![Layer 3](../assets/FLORA_Third_Lasyer_Architecture.png) | FLORA 推論と統合 |

---

## FarmMonitor

![FarmMonitor アーキテクチャ](../assets/Farm_Monitor_Core_Architecture.png)

スケジュールに従って圃場全体をスキャンします。フレームのバッチをキャプチャし、ブレた画像を除去してから病害・熟度検出を実行します。

![FarmMonitor 結果](../assets/Farm_Monitor_Result.png)

結果は `runtime/farmmonitor/` に JSON + JPEG として保存されます。病害が検出されて SMTP が設定されていれば、メールでアラートを送信します。

---

## セキュリティカメラ

![セキュリティカメラ結果](../assets/Security_camera_result.png)

フレームスキップ推論（N フレーム毎）とクラス許可リストで CPU 負荷を抑えます。脅威検出時はサイレンが 8 秒作動し、スナップショットを保存します。

---

## Meshtastic LoRa ブリッジ

![Meshtastic](../assets/MEshtastic.png)

`.env` で `MESH_ENABLED=true` を設定し、`MESH_HOST` を自分のノードに向けます。FLORA は任意のチャンネル / DM を待ち受け、送信元にのみ返信します — 完全オフグリッドで動作します。

---

## ストレージ

![Storage](../assets/Storage_Data_screenshot.png)

キャプチャしたフレーム、農場スキャン、セキュリティ・スナップショットは、ダッシュボードの Events タブとストレージ API から閲覧できます。

---

## カメラ設定

```bash
# Raspberry Pi CSI カメラ（コマンドラインの --input で指定）
python main.py --input csi:0

# USB カメラ
python main.py --input /dev/video0

# ネットワーク / RTSP カメラ
python main.py --input rtsp://user:pass@192.168.1.10/live
```


---

## 🧠 自分の ML モデルを差し込む

病害・熟度ディテクタは **Ultralytics YOLO の `.pt` ファイル** にすぎません。
自分の作物で学習した `.pt` を `main.py` と同じ階層の `models/` フォルダに置けばアプリが拾います。

```bash
# デフォルトは FarmMonitor の作業ディレクトリにあります。
# 以下のように自前のモデルを上書きすれば次のスキャンから使われます:
cp my_strawberry_disease.pt   FarmMonitor_Work/Disease_detect.pt
cp my_tomato_ripeness.pt      FarmMonitor_Work/Ripeness_detect.pt
```

**セキュリティカメラ** は `.env` の `PLANTWATCH_SECURITY_HEF` に `.hef` ファイルへのパスを設定すれば Hailo 経路で動きます。未設定なら CPU YOLO のデフォルトが使われます。

同梱のイチゴ用モデルは出発点であり、必須ではありません。

---

## Hailo（オプション）

```bash
# まずホスト側に HailoRT SDK をインストールし、Hailo 用の入力フラグで起動:
python main.py --input /dev/video0 --arch hailo10h --use-frame
```

---

## CLI リファレンス

```
python main.py [options]

  --input             カメラ入力（csi:N | /dev/videoN | rtsp://... | path）
  --arch              hailo10h | cpu （デフォルト: cpu）
  --use-frame         Hailo のフレームごとコールバックを使う（Hailo 用）
  --use-rpicam        picamera2 (libcamera) キャプチャ経路を使う
```

ポート、JPEG 品質、FPS、セキュリティ HEF パスなどのその他のオプションはすべて環境変数です — `.env.example` を参照してください。

---

## プロジェクト構成

```
AIgriculture/
├── main.py                       # メインアプリ：ダッシュボード + センサー + 灌漑
├── dashboard.html               # ダッシュボード（シングルページ アプリ）
├── login.html                          # ログイン画面
├── farm_monitor_designer_email.py      # 通知メールのテンプレート
├── farm_monitor_pt_scan.py             # 病害・熟度の .pt スキャナ
├── farm_monitor_disease_labels.json    # 病害クラス（YOLO ラベル）
├── farm_monitor_ripeness_labels.json   # 熟度クラス（YOLO ラベル）
├── flora_agent.py / flora_config.py    # FLORA AI アシスタント
├── flora_report.py / flora_scheduler.py / flora_tools.py
├── meshtastic_flora_bridge.py          # LoRa ブリッジ
├── ../assets/                        # README で使用する画像
├── .env.example                        # ← .env にコピーして編集
├── config.example.yaml                 # ← config.yaml にコピーして編集（メール用）
├── wiring.example.yaml                 # ← wiring.yaml にコピーして編集（独自ピン用）
└── requirements.txt
```

---

## ライセンス

MIT — [LICENSE](LICENSE) を参照してください。
