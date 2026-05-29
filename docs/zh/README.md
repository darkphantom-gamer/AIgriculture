<div align="center">

#  AIgriculture

**面向 Raspberry Pi 的开源智能农场系统。**
监测土壤湿度、自动灌溉、检测病害，并与你的农场进行 AI 对话 — 全部通过一个网页仪表盘。

[![English](https://img.shields.io/badge/lang-English-blue?style=for-the-badge)](../../README.md)
[![日本語](https://img.shields.io/badge/lang-日本語-red?style=for-the-badge)](../ja/README.md)
[![हिन्दी](https://img.shields.io/badge/lang-हिन्दी-orange?style=for-the-badge)](../hi/README.md)
[![Русский](https://img.shields.io/badge/lang-Русский-green?style=for-the-badge)](../ru/README.md)
[![中文](https://img.shields.io/badge/lang-中文-red?style=for-the-badge)](README.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-Pi%20native%20(3.13)-blue.svg)](https://www.python.org/downloads/)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-4%20%7C%205-c51a4a)](https://www.raspberrypi.com/)

</div>

---

![农场总览](../assets/small_prototype.jpeg)

---

## 它能做什么

| 子系统 | 提供的功能 |
|--------|-----------|
| **灌溉** | 任意盆数的脉冲式灌溉，自动模式（45 % 启动、65 % 停止、70 % 硬锁） |
| **FarmMonitor** | 定时 YOLO 扫描 — 病害（5 类）和成熟度（5 阶段），检出后发送邮件提醒 |
| **安防摄像头** | 实时人/动物检测，双蜂鸣器警报，仪表盘 MJPEG 视频流 |
| **FLORA AI** | 多服务商聊天助手（Groq / Cerebras / Mistral / Gemini），可调用农场工具，离线降级 |
| **Meshtastic** | LoRa 桥接 — FLORA 会回应你 mesh 网络上的任意频道或私聊 |
| **仪表盘** | 暗色单页应用：概览、摄像头、AI 聊天、事件日志、设置 |

仓库提供 **两个入口** — 按硬件挑一个：

| 脚本 | 适用场景 | 安防摄像头推理引擎 |
|------|----------|-------------------|
| **`python main.py`** | 默认。任意 Raspberry Pi (4 / 5) 或笔记本都可以跑。 | Ultralytics YOLOv8n 在 CPU 上跑，带 frame-skip — 普通 Pi 即可。 |
| **`python main-hailo.py`** | 已安装 Hailo-10H AI HAT 时。 | Hailo HEF 流水线 — 推理快约 10×。 |

其余部分（仪表盘、登录、FLORA、FarmMonitor、灌溉、邮件提醒、存储、Meshtastic）两脚本 **完全一致**。唯一区别就是安防摄像头的推理引擎。

---

## 🛠️ 硬件 — 新手 / 测试套件

还没有真正的农场？**没关系。** 下面是把 AIgriculture 跑成桌面原型所需的最小套件。每一行都是适合新手的替代方案。

| # | 部件 | 为什么需要 | 新手提示 |
|---|------|------------|-----------|
| 1 | **Raspberry Pi 4 / 5**（4 GB+，推荐 8 GB）<br><img src="../assets/hardware/Raspberrypi_5.png" width="240"> | 运行整个系统 — 仪表盘、AI、灌溉逻辑。 | Pi 5 最快，但 Pi 4 (2 GB) 也可以试。烧录 **Raspberry Pi OS Bookworm 64-bit**。 |
| 2 | **ADS1115 16-bit I²C ADC**<br><img src="../assets/hardware/adc_module.png" width="240"> | Pi 没有模拟输入；电容式湿度传感器是模拟信号，ADC 把它转成数字。 | 一片 ADS1115 = 4 个传感器。按需添加 — **四片**（`0x48`-`0x4B`）可支持 16 盆，再加 I²C 总线还能更多。 |
| 3 | **电容式土壤湿度传感器**<br><img src="../assets/hardware/moisture_sensor.png" width="240"> | 读取土壤湿度 — 自动灌溉的输入。 | 一定选 **电容式**（黄色 PCB），便宜的电阻式几周就会腐蚀。每盆植物一个。 |
| 4 | **8 路继电器板**（active-LOW、光耦隔离）<br><img src="../assets/hardware/relay_module.png" width="240"> | 让 Pi 切换水泵开关。Pi 自身无法供给水泵电流。 | 必须标注 **5V trigger、opto-isolated**，否则 3.3V GPIO 触发不了。 |
| 5 | **小型 5V 或 12V DC 水泵**<br><img src="../assets/hardware/water_pump.png" width="240"> | 真正给植物浇水的部件。 | 每盆一个。**务必单独供电，绝不能用 Pi 的 5V 引脚。** Pi 只控制继电器。 |
| 6 | **Raspberry Pi 摄像头（CSI）** *或* **USB 摄像头**<br><img src="../assets/hardware/pi-camera.jpeg" width="200"> &nbsp; <img src="../assets/hardware/usb_camera.png" width="200"> | 一个用于 FarmMonitor 病害/成熟扫描，一个用于安防摄像头。 | 起步一个摄像头也够 — 传 `--security-camera` 跳过 `--farm-camera`。也支持 RTSP IP 摄像头。 |
| 7 | **面包板 + 杜邦线**<br><img src="../assets/hardware/breadboard_and_jumper_wires.png" width="240"> | 无需焊接连接全部部件。 | 传感器 → ADC 用母对母，ADC → Pi 用公对母。 |
| **+** | **Hailo-10H AI HAT** *(可选，加速 CV)*<br><img src="../assets/hardware/hailo10h_optional.png" width="240"> | 硬件加速 YOLO 推理，大幅缩短病害/成熟度扫描时间。 | **新手套件可跳过。** 普通 Pi 的 CPU 路径也跑得动。需要加速时再加。 |
| **+** | **Meshtastic LoRa 电台** *(可选，无网离线聊天)*<br><img src="../assets/hardware/LORA_chip_with_433hz_antenna.png" width="240"> | 在 Wi-Fi 覆盖外通过 LoRa mesh 与 FLORA 聊天。 | 可选。Heltec / LilyGo 板配 433 / 868 / 915 MHz 天线都行。只要 web UI 就跳过。 |

**最小测试套件**（只为在桌面上玩一下仪表盘）:
> 1 × Pi · 1 × ADS1115 · 1 × 湿度传感器 · 1 × USB 摄像头。就这些。不需要继电器、水泵、Hailo。等仪表盘起来后用 "+ Add sensors" 按钮添加更多。

---

## 🚀 快速开始

```bash
git clone https://github.com/darkphantom-gamer/AIgriculture.git
cd AIgriculture
cp .env.example .env            # 然后编辑 .env（见下一节）
python main.py
```

打开 `http://<pi-ip>:8000`。

> **在笔记本/非 Pi 上运行？** 也能跑。硬件不在时 GPIO 和 I2C 会静默 no-op — 仪表盘、AI 聊天、(USB/网络) 摄像头照常可用。

> **想要原生安装？**
> ```bash
> pip install -r requirements.txt --break-system-packages
> python main.py
> ```

---

## 🔑 必须填写你自己的凭据

**仓库中不包含任何真实 API key、密码或邮箱 — 这是有意的设计。**
`cp .env.example .env` 之后，打开 `.env` 填上你自己的：

| `.env` 字段 | 填什么 | 在哪里申请 |
|-------------|-------|-----------|
| `ADMIN_USER` | 仪表盘用户名（自己定） | （自己决定） |
| `ADMIN_PASS` | 强密码 | （自己决定） |
| `GROQ_API_KEY` | Groq 的 key（推荐，快且免费） | https://console.groq.com |
| `CEREBRAS_API_KEY` | Cerebras 的 key（可选） | https://cloud.cerebras.ai |
| `MISTRAL_API_KEY` | Mistral 的 key（可选） | https://console.mistral.ai |
| `GEMINI_API_KEY` | Google AI Studio key（可选） | https://aistudio.google.com |

只要设置 **任意一个** AI 服务商，FLORA 就具备完整的工具调用聊天能力。全部留空也没关系 — FLORA 会用关键词路由离线工作。

需要 **邮件告警**（FarmMonitor 病害通知、FLORA 报告）：
```bash
cp config.example.yaml config.yaml      # 然后编辑 config.yaml
```

在 `config.yaml` 里写自己的 SMTP — Gmail（用 *App Password*）、Hostinger、学校邮件，任何支持 SMTP 的都行：

```yaml
smtp:
  host: smtp.gmail.com          # 或 smtp.hostinger.com、smtp.office365.com 等
  port: 587
  email: you@your-domain.com    # 你真实的发件邮箱
  password: your-app-password   # 不是普通密码 — 是 App Password
  from_email: you@your-domain.com
notifications:
  to_email: alerts@your-domain.com
```

> **Gmail 小贴士：** 先打开两步验证，然后在 https://myaccount.google.com/apppasswords 创建 **App Password** 并粘贴。普通 Gmail 密码会被 SMTP 拒绝。

`.env` 和 `config.yaml` 都已加入 `.gitignore` — 你的真实秘密不会进入仓库。

---

## 🔌 接线（改一个文件即可适配你的板子）

默认引脚映射（`main.py` 出厂值）：

| 部件 | 默认 BCM 引脚 |
|------|----------------|
| 8 路水泵继电器（植物 A → H） | `17, 27, 22, 23, 5, 6, 13, 19`（active LOW） |
| 2 个蜂鸣器警报 | `18, 12`（2700 Hz） |
| 8 路湿度传感器 | 两片 ADS1115，I²C 地址 `0x48` 和 `0x49` |
| I²C 总线 | `/dev/i2c-1` |
| GPIO 芯片 | `/dev/gpiochip0`（Pi 5 自动回退到 `4`） |

**想换引脚？** 不需要改 Python：

```bash
cp wiring.example.yaml wiring.yaml      # 然后编辑 wiring.yaml
python main.py
```

通过 `wiring.yaml` 可以重映射任意引脚、切换 active-high/low、修改蜂鸣器数量和频率、重新校准湿度传感器 — 全程不动代码。

---

## 📡 Meshtastic LoRa 桥（进程内）

在 `.env` 中设置 `MESH_ENABLED=true`，`main.py` 和 `main-hailo.py` 都会在**同一个进程内**启动 Meshtastic ↔ FLORA 桥，不需要额外启动服务。该桥：

- 通过 TCP 连接本地 `meshtasticd`（默认 `localhost:4403`）
- 监听任意频道或私聊
- 通过进程内 HTTP API 转发消息给 FLORA
- 在收到请求的同一频道回复

![Meshtastic ↔ FLORA 真实 LoRa 聊天](../img/meshtastic-flora-proof.jpg)

Meshtastic 库未安装或连接断开时，桥只打印警告日志，`main.py` 继续运行 — 仪表盘永不阻塞。

`MESH_*` 全部可调参数（允许节点、回复模式、频道过滤）见 `.env.example`。

---

## ➕ 运行时增加传感器

仪表盘右上角有 **"+ Add sensors"** 按钮（仅管理员可见）。点击后程序会：

1. 扫描所有 4 个 ADS1115 地址（`0x48`-`0x4B`）× 各 4 通道
2. 找到读数合理且尚未占用的通道
3. 把它们注册为新植物（字母 `i`-`p`，最多 16 个）并持久化到 `.plants.json`
4. 立即开始轮询 — 无需重启或改代码

适合从 2 个传感器的试装方案开始、后续扩容的场景。

---

## 仪表盘

![仪表盘状态](../assets/dashboard_status.png)

五个标签页：**Overview**（实时湿度 + 水泵控制）、**Cameras**（MJPEG 视频流）、**FLORA**（AI 聊天）、**Events**（告警日志）、**Settings**（通知 + 警报器）。

---

## FLORA AI 助手

![FLORA 预览](../assets/FLORA_preview.jpeg)

FLORA 能理解自然语言命令：

- *"给植物 A 浇水"* → 触发脉冲灌溉
- *"所有植物现在的湿度是多少？"* → 读取全部传感器
- *"停止 C 号水泵"* → 关掉水泵 C
- *"现在检测到病害了吗？"* → 查看最新 FarmMonitor 扫描

未配置 API key 时，FLORA 仍可通过关键词路由完全离线工作。

### 架构

| 层 | 角色 |
|----|------|
| ![Layer 1](../assets/FLORA_first_layer_Architecture.png) | 服务商路由 + 回退 |
| ![Layer 2](../assets/FLORA_Second_layer_Architecture.png) | 工具分发（传感器、水泵、摄像头、调度器） |
| ![Layer 3](../assets/FLORA_Third_Lasyer_Architecture.png) | FLORA 推理与集成 |

---

## FarmMonitor

![FarmMonitor 架构](../assets/Farm_Monitor_Core_Architecture.png)

按计划对整块田进行扫描。捕获一组帧，剔除模糊的，再运行病害和成熟度检测。

![FarmMonitor 结果](../assets/Farm_Monitor_Result.png)

结果以 JSON + JPEG 保存在 `runtime/farmmonitor/`。若检测到病害且 SMTP 已配置，则发送邮件告警。

---

## 安防摄像头

![安防摄像头结果](../assets/Security_camera_result.png)

跳帧推理（每 N 帧）+ 类别白名单保持 CPU 占用低。检测到威胁时警报器响 8 秒并保存截图。

---

## Meshtastic LoRa 桥

![Meshtastic](../assets/MEshtastic.png)

在 `.env` 设置 `MESH_ENABLED=true` 并把 `MESH_HOST` 指向你的节点。FLORA 会监听任意频道或私聊，只回复发送者 — 完全离线运行。

---

## 存储

![Storage](../assets/Storage_Data_screenshot.png)

所有捕获帧、农场扫描和安防截图都可通过仪表盘 Events 标签页和存储 API 浏览。

---

## 摄像头选项

```bash
# Raspberry Pi CSI 摄像头（通过 --input 指定）
python main.py --input csi:0

# USB 摄像头
python main.py --input /dev/video0

# 网络 / RTSP 摄像头
python main.py --input rtsp://user:pass@192.168.1.10/live
```


---

## 🧠 接入你自己的 ML 模型

病害和成熟度检测器就是 **Ultralytics YOLO 的 `.pt` 文件**。
用自己的作物训练后，放到 `main.py` 旁边的 `models/` 文件夹，应用会自动捡起。

```bash
# 默认权重在 FarmMonitor 的工作目录。
# 用你自己的 .pt 替换，下次扫描即生效：
cp my_strawberry_disease.pt   FarmMonitor_Work/Disease_detect.pt
cp my_tomato_ripeness.pt      FarmMonitor_Work/Ripeness_detect.pt
```

**安防摄像头**：在 `.env` 设置 `PLANTWATCH_SECURITY_HEF` 指向你的 `.hef` 文件（Hailo），否则使用默认 CPU YOLO 路径。

随仓库提供的草莓模型只是起点，并不是硬性要求。

---

## Hailo（可选）

```bash
# 先在主机上安装 HailoRT SDK，然后用 Hailo 输入参数启动：
python main.py --input /dev/video0 --arch hailo10h --use-frame
```

---

## CLI 参考

```
python main.py [options]

  --input             摄像头输入（csi:N | /dev/videoN | rtsp://... | path）
  --arch              hailo10h | cpu（默认：cpu）
  --use-frame         使用 Hailo 逐帧回调（Hailo 专用）
  --use-rpicam        使用 picamera2 (libcamera) 捕获路径
```

其他选项（端口、JPEG 质量、FPS、安防 HEF 路径）都是环境变量 — 见 `.env.example`。

---

## 项目结构

```
AIgriculture/
├── main.py                       # 主应用：仪表盘 + 传感器 + 灌溉
├── dashboard.html               # 仪表盘（单页应用）
├── login.html                          # 登录页
├── farm_monitor_designer_email.py      # 告警邮件模板
├── farm_monitor_pt_scan.py             # 病害 + 成熟度 .pt 扫描器
├── farm_monitor_disease_labels.json    # 病害 YOLO 类别标签
├── farm_monitor_ripeness_labels.json   # 成熟度 YOLO 类别标签
├── flora_agent.py / flora_config.py    # FLORA AI 助手
├── flora_report.py / flora_scheduler.py / flora_tools.py
├── meshtastic_flora_bridge.py          # LoRa 桥
├── ../assets/                        # README 中使用的图片
├── .env.example                        # ← 复制为 .env 并编辑
├── config.example.yaml                 # ← 复制为 config.yaml（用于邮件）
├── wiring.example.yaml                 # ← 复制为 wiring.yaml（用于自定义引脚）
└── requirements.txt
```

---

## 许可证

MIT — 详见 [LICENSE](LICENSE)。
