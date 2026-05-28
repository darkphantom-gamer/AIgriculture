<div align="center">

# 🌱 AIgriculture

**Raspberry Pi 向けオープンソース スマートファームシステム**
土壌水分の監視、自動灌水、病害検出、AIとのチャット — すべてひとつのウェブダッシュボードで。

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

![ファーム全体](docs/assets/big_farm.jpeg)

---

## 機能一覧

| サブシステム | 概要 |
|------------|------|
| **自動灌水** | 8植物対応バースト灌水。水分が45%以下で起動、65%以上で停止、70%以上でハードロック |
| **FarmMonitor** | YOLO による定期スキャン — 病害5クラス・熟度5段階。検出時にメール通知 |
| **セキュリティカメラ** | リアルタイム人物/動物検出、デュアルブザーサイレン、MJPEG ストリーム |
| **FLORA AI** | Groq / Cerebras / Mistral / Gemini 対応チャットアシスタント。オフライン対応 |
| **Meshtastic** | LoRa ブリッジ — メッシュネットワーク経由でFLORAに話しかけられる |
| **ダッシュボード** | ダークテーマのシングルページアプリ（概要・カメラ・AI・イベント・設定） |

---

## ハードウェア

![プロトタイプ](docs/assets/small_prototype.jpeg)

| 部品 | 詳細 |
|-----|------|
| Raspberry Pi 4/5 | 2GB以上RAM、64ビット OS Bookworm |
| ADS1115 × 2 | I2C ADC（0x48, 0x49）— 水分センサー8チャンネル |
| 8チャンネルリレー基板 | アクティブLow、BCM 17 27 22 23 5 6 13 19 |
| ブザー × 2 | BCM 18, 12（2700 Hz） |
| Pi Camera × 2 | CSI — セキュリティ(csi:0) + FarmMonitor(csi:1) |
| *(オプション)* Hailo-8 M.2 | ハードウェアAIアクセラレーター |

配線の詳細は [`aigriculture.txt`](aigriculture.txt) を参照してください。

---

## 🚀 クイックスタート

```bash
git clone https://github.com/darkphantom-gamer/AIgriculture.git
cd AIgriculture
cp .env.example .env   # 必ず編集してください（下記参照）
docker compose up -d
```

ブラウザで `http://<pi-ip>:8000` を開きます。

> Pi 以外（ノートPCなど）でも動きます。GPIO と I2C はハードがなければ自動で無効化されるので、ダッシュボード・AIチャット・USB/ネットワークカメラはそのまま利用できます。

ネイティブインストール・systemdサービス・Hailo については [docs/SETUP.md](docs/SETUP.md) を参照してください。

---

## 🔑 自分の認証情報を必ず追加してください

**このリポジトリには本物のAPIキー、パスワード、メールアドレスは一切含まれていません。**
`.env` をコピーした後、必ず開いて自分の情報を入れてください。

| `.env` の項目 | 内容 | 取得先 |
|--------------|-----|-------|
| `ADMIN_USER` | ダッシュボードのユーザー名 | （自分で決める） |
| `ADMIN_PASS` | 強いパスワード | （自分で決める） — 空欄なら初回起動時にランダム生成されコンソールに表示されます |
| `GROQ_API_KEY` | Groq のキー（推奨・無料・高速） | https://console.groq.com |
| `CEREBRAS_API_KEY` | Cerebras のキー（任意） | https://cloud.cerebras.ai |
| `MISTRAL_API_KEY` | Mistral のキー（任意） | https://console.mistral.ai |
| `GEMINI_API_KEY` | Google AI Studio のキー（任意） | https://aistudio.google.com |

AIプロバイダーの**いずれか1つでも**設定すれば FLORA がツール対応のフルチャットモードに入ります。全部空でもキーワードベースでオフライン動作します。

**メール通知**（FarmMonitor の病害アラート / FLORA レポート）を有効にするには：
```bash
cp config.example.yaml config.yaml      # 編集してください
```

`config.yaml` の中で、自分の SMTP 情報を入れてください — Gmail（**アプリパスワード**必須）、Hostinger、独自ドメイン、何でも構いません：

```yaml
smtp:
  host: smtp.gmail.com
  port: 587
  email: you@your-domain.com
  password: your-app-password   # 通常のパスワードではなく「アプリパスワード」
  from_email: you@your-domain.com
notifications:
  to_email: alerts@your-domain.com
```

> **Gmail のコツ:** 2段階認証を有効にしてから https://myaccount.google.com/apppasswords でアプリパスワードを発行してください。

`.env` と `config.yaml` は両方とも `.gitignore` 対象なので、リポジトリに本物の情報が混入することはありません。

---

## 🔌 配線（1ファイル編集するだけ）

デフォルトのピン配置：

| 部品 | デフォルト BCM ピン |
|-----|------|
| 8系統のリレー（A → H） | `17, 27, 22, 23, 5, 6, 13, 19`（アクティブLOW） |
| ブザー2個 | `18, 12`（2700 Hz） |
| 湿度センサー | ADS1115 × 2、`0x48` と `0x49` |

**ピン配置を変えるとき**は Python ファイルを編集する必要はありません：

```bash
cp wiring.example.yaml wiring.yaml      # 編集してください
docker compose up -d --force-recreate
```

---

## ダッシュボード

![ダッシュボード](docs/assets/dashboard_status.png)

5つのタブ: **概要**（リアルタイム水分＋ポンプ操作）、**カメラ**（MJPEGストリーム）、**FLORA**（AIチャット）、**イベント**（アラートログ）、**設定**（通知・サイレン）。

---

## FLORA AIアシスタント

![FLORA](docs/assets/FLORA_preview.jpeg)

FLORAは自然言語コマンドを理解します：

- *「植物Aに水をやって」* → バースト灌水を開始
- *「全植物の水分レベルを教えて」* → センサー値を一括読み取り
- *「病気は検出されていますか？」* → 最新のFarmMonitorスキャンを確認

APIキーが設定されていない場合、FLORAはキーワードルールでオフライン動作します。

---

## FarmMonitor

![Farm Monitorアーキテクチャ](docs/assets/Farm_Monitor_Core_Architecture.png)

定期スキャンを実行し、フレームを取得、ブレを除外、病害・熟度を検出します。

![Farm Monitor結果](docs/assets/Farm_Monitor_Result.png)

結果は `runtime/farmmonitor/` にJSON+JPEGで保存されます。

---

## セキュリティカメラ

![セキュリティカメラ](docs/assets/Security_camera_result.png)

フレームスキップとクラスフィルターでCPU負荷を抑制。脅威検知時にサイレンが8秒間作動し、スナップショットが保存されます。

---

## カメラ設定

```bash
# CSIカメラ
python -m aigriculture --security-camera csi:0 --farm-camera csi:1

# USBカメラ
python -m aigriculture --security-camera /dev/video0

# ネットワーク(RTSP)カメラ
python -m aigriculture --security-camera rtsp://192.168.1.10/live
```

---

## ライセンス

MIT — [LICENSE](LICENSE) を参照してください。
