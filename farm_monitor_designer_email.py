#!/usr/bin/env python3
"""
Send a branded AIgriculture Farm Monitor detection email.

This script is intentionally standalone so FarmMonitor email design can be
tested without rerunning the full camera pipeline. It reads config_demo.yaml
locally, but never prints SMTP credentials or recipient addresses.
"""
from __future__ import annotations

import argparse
import html
import mimetypes
import smtplib
import sys
from datetime import datetime
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = BASE_DIR / "config_demo.yaml"


def read_simple_yaml(path: Path) -> dict:
    """Read the simple section/key YAML style used by config_demo.yaml."""
    cfg: dict[str, dict[str, str]] = {}
    section = None
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not raw.startswith((" ", "\t")) and line.endswith(":"):
            section = line[:-1].strip()
            cfg.setdefault(section, {})
            continue
        if section and ":" in line:
            key, value = line.split(":", 1)
            cfg.setdefault(section, {})[key.strip()] = value.strip().strip("'\"")
    return cfg


def pct(value: float) -> str:
    return f"{round(float(value) * 100)}%"


def event_style(event_type: str) -> dict:
    if event_type == "security":
        return {
            "accent": "#dc2626",
            "accent2": "#991b1b",
            "soft": "#fff1f2",
            "page": "#fff7f7",
            "pill": "Security Alert",
            "icon": "!",
            "dot": "#ef4444",
            "title": "Farm activity detected",
            "headline": "Security activity was detected near the farm area.",
            "next_stage": "Check camera",
            "recommendation": "Open the dashboard and review the attached camera picture.",
            "footer": "Security updates are sent only when guard mode records activity.",
        }
    if event_type == "disease":
        return {
            "accent": "#7c3aed",
            "accent2": "#5b21b6",
            "soft": "#f5f3ff",
            "page": "#fbf8ff",
            "pill": "Plant Health Alert",
            "icon": "!",
            "dot": "#8b5cf6",
            "title": "Plant health warning",
            "headline": "A plant health issue needs attention.",
            "next_stage": "Inspect plant",
            "recommendation": "Review the marked picture and inspect the affected plant area before handling or harvest.",
            "footer": "Health warnings are sent when plant disease signs are sustained across the scan.",
        }
    if event_type == "disease_and_ripeness":
        return {
            "accent": "#d97706",
            "accent2": "#7c2d12",
            "soft": "#fffbeb",
            "page": "#fffaf0",
            "pill": "Health + Harvest",
            "icon": "*",
            "dot": "#f59e0b",
            "title": "Harvest is ready, but check plant health",
            "headline": "Harvest signs are present, but plant health needs attention.",
            "next_stage": "Check before harvest",
            "recommendation": "Review both attached frames. Harvest-ready fruit may need separation if disease appears on the same plant area.",
            "footer": "Combined updates are sent when harvest-readiness and plant-health warnings appear together.",
        }
    if event_type == "ripeness":
        return {
            "accent": "#0d8a78",
            "accent2": "#0f766e",
            "soft": "#ecfdf5",
            "page": "#f0fdf9",
            "pill": "Harvest Readiness",
            "icon": "✓",
            "dot": "#22c55e",
            "title": "Good news from your farm",
            "headline": "The plant is showing ready-to-harvest fruit.",
            "next_stage": "Harvest now",
            "recommendation": "Review the attached marked picture and plan harvest inspection for the highlighted ripe fruit.",
            "footer": "Harvest updates are sent when ripeness signs are sustained across the scan.",
        }
    return {
        "accent": "#475569",
        "accent2": "#334155",
        "soft": "#f8fafc",
        "page": "#f8fafc",
        "pill": "Farm Monitor",
        "icon": "i",
        "dot": "#64748b",
        "title": "Your field update is ready",
        "headline": "No sustained event was detected in this scan.",
        "next_stage": "Keep monitoring",
        "recommendation": "No sustained plant-health or harvest-readiness event was detected in this scan.",
        "footer": "Farm Monitor keeps scanning on schedule.",
    }


def build_html(args: argparse.Namespace, image_cids: list[str]) -> str:
    style = event_style(args.event_type)
    generic_titles = {"", "your field update is ready", "farm update", "aigriculture update"}
    title = style["title"] if (args.title or "").strip().lower() in generic_titles else args.title
    now = args.time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    primary_label = args.detection_label or ("Ripe" if args.event_type == "ripeness" else "Detection")
    disease_signal = pct(args.disease_ratio)
    harvest_signal = pct(args.ripeness_ratio)
    message = args.message or style["headline"]
    dashboard_url = args.dashboard_url or "http://raspberrypi:8000"
    table_title = "Detected farm activity" if args.event_type == "security" else "Detected crop details"
    crop_stage_rows = args.rows or []
    if not crop_stage_rows:
        crop_stage_rows = [
            f"{primary_label}|Detected|{style['next_stage']}",
            f"Harvest update|{'Ready' if args.event_type in ('ripeness', 'disease_and_ripeness') else 'Normal'}|Review field",
            f"Plant health update|{'Needs attention' if args.event_type in ('disease', 'disease_and_ripeness') else 'Normal'}|Monitor",
        ]

    table_rows = []
    for raw in crop_stage_rows:
        parts = [p.strip() for p in raw.split("|")]
        while len(parts) < 3:
            parts.append("")
        what, conf, stage = parts[:3]
        table_rows.append(f"""
          <tr>
            <td style="padding:12px 12px;border-top:1px solid #dfe9dd;color:#20312d;font-size:14px;line-height:1.35">
              <span style="display:inline-block;width:9px;height:9px;border-radius:999px;background:{style['dot']};vertical-align:middle;margin-right:8px"></span>{html.escape(what)}
            </td>
            <td style="padding:12px 12px;border-top:1px solid #dfe9dd;color:#20312d;font-size:14px;font-weight:800;text-align:center">{html.escape(conf)}</td>
            <td style="padding:12px 12px;border-top:1px solid #dfe9dd;color:#20312d;font-size:14px;line-height:1.35;text-align:right">{html.escape(stage)}</td>
          </tr>
        """)

    image_blocks = ""
    if image_cids:
        cards = []
        for i, cid in enumerate(image_cids, start=1):
            label = "scanned.jpg" if i == 1 else f"supporting-frame-{i}.jpg"
            cards.append(
                f"""
                <div style="margin-top:16px;border-radius:18px;overflow:hidden;background:#ffffff;border:1px solid #d9e8d7">
                  <img src="cid:{cid}" width="560" alt="{html.escape(label)}" style="display:block;width:100%;max-width:560px;height:auto;margin:0 auto">
                  <div style="padding:10px 14px;background:{style['soft']};color:#2f332f;font-size:13px;line-height:1.45">Attached farm image: {html.escape(label)}</div>
                </div>
                """
            )
        image_blocks = "".join(cards)
    else:
        image_blocks = """
        <div style="margin-top:16px;padding:16px;border:1px dashed #a7dcd2;border-radius:16px;color:#53726b;background:#f8fffd">
          No image attachment was provided for this alert.
        </div>
        """

    return f"""<!doctype html>
<html>
  <head>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>
      @media only screen and (max-width:620px){{
        .wrap{{padding:14px 10px!important}}
        .card{{border-radius:22px!important}}
        .hero{{padding:24px 18px!important}}
        .body{{padding:22px 18px!important}}
        .title{{font-size:25px!important;line-height:1.12!important}}
        .subtitle{{font-size:14px!important}}
        .headline{{font-size:20px!important;line-height:1.35!important}}
        .time{{font-size:13px!important}}
        .btn{{display:block!important;text-align:center!important;padding:15px 18px!important;font-size:15px!important}}
        .table-title{{font-size:17px!important}}
        th,td{{font-size:12px!important;padding-left:8px!important;padding-right:8px!important}}
      }}
    </style>
  </head>
  <body style="margin:0;background:{style['page']};font-family:Arial,Helvetica,sans-serif;color:#20312d;-webkit-text-size-adjust:100%;text-size-adjust:100%">
    <div style="display:none;max-height:0;overflow:hidden">{html.escape(title)} - {html.escape(message)}</div>
    <div class="wrap" style="max-width:600px;margin:0 auto;padding:20px 12px;background:{style['page']}">
      <div class="card" style="border-radius:24px;overflow:hidden;background:#ffffff;border:1px solid #d8e8d6;box-shadow:0 12px 34px rgba(19,78,74,.10)">
        <div class="hero" style="padding:30px 28px 26px;background:linear-gradient(135deg,{style['soft']},#ffffff);border-bottom:1px solid #d9e8d7">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
            <tr>
              <td style="width:58px;vertical-align:top">
                <div style="width:48px;height:48px;border-radius:16px;background:#ffffff;text-align:center;line-height:48px;color:{style['accent']};font-size:25px;font-weight:900;border:1px solid #d9e8d7">{html.escape(style['icon'])}</div>
              </td>
              <td>
                <div class="title" style="font-size:30px;line-height:1.13;font-weight:900;color:#20312d">{html.escape(title)}</div>
                <div class="subtitle" style="font-size:15px;line-height:1.45;color:#61705f;margin-top:8px">AIgriculture farm notification</div>
              </td>
            </tr>
          </table>
        </div>

        <div class="body" style="padding:28px;background:#ffffff">
          <div style="display:inline-block;border:1px solid #d7ead3;background:{style['soft']};border-radius:999px;padding:9px 14px;color:{style['accent']};font-size:13px;font-weight:800">
            <span style="display:inline-block;width:9px;height:9px;border-radius:999px;background:{style['dot']};vertical-align:middle;margin-right:8px"></span>{html.escape(style['pill'])}
          </div>

          <div class="headline" style="font-size:23px;line-height:1.38;font-weight:850;color:#20312d;margin-top:20px">{html.escape(message)}</div>
          <div class="time" style="font-size:14px;line-height:1.7;color:#52635f;margin-top:12px">Time: {html.escape(now)}</div>

          <div style="margin-top:24px;border:1px solid #d9e8d7;border-radius:18px;overflow:hidden;background:#ffffff">
            <div class="table-title" style="padding:16px 18px;color:#2f5234;font-size:18px;font-weight:900">{html.escape(table_title)}</div>
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse">
              <tr>
                <th align="left" style="padding:12px;background:#edf8e8;color:#20312d;font-size:13px;line-height:1.25">What was detected</th>
                <th align="center" style="padding:12px;background:#edf8e8;color:#20312d;font-size:13px;line-height:1.25">Status</th>
                <th align="right" style="padding:12px;background:#edf8e8;color:#20312d;font-size:13px;line-height:1.25">Next stage</th>
              </tr>
              {''.join(table_rows)}
            </table>
          </div>

          <div style="font-size:14px;line-height:1.65;color:#4d5e58;margin-top:22px">
            The clearest marked picture is attached as <strong>scanned.jpg</strong> when available.
          </div>

          <div style="margin-top:28px">
            <a class="btn" href="{html.escape(dashboard_url)}" style="display:inline-block;text-decoration:none;background:linear-gradient(180deg,{style['accent']},{style['accent2']});color:white;font-size:16px;font-weight:900;border-radius:16px;padding:15px 22px">Open dashboard</a>
          </div>

          {image_blocks}
        </div>

        <div style="padding:16px 28px;background:#f7fff2;border-top:1px solid #d9e8d7;color:#61705f;font-size:12px;line-height:1.55">
          {html.escape(style['footer'])}
        </div>
      </div>
    </div>
  </body>
</html>"""


def attach_images(msg: EmailMessage, image_paths: list[Path], cids: list[str]) -> None:
    html_part = msg.get_payload()[1]
    for image_path, cid in zip(image_paths, cids):
        if not image_path.exists() or not image_path.is_file():
            raise FileNotFoundError(f"Attachment not found: {image_path}")
        ctype, _ = mimetypes.guess_type(str(image_path))
        maintype, subtype = (ctype or "image/jpeg").split("/", 1)
        data = image_path.read_bytes()
        html_part.add_related(data, maintype=maintype, subtype=subtype, cid=f"<{cid}>", filename="scanned.jpg" if image_path == image_paths[0] else image_path.name)
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename="scanned.jpg" if image_path == image_paths[0] else image_path.name)


def send_email(args: argparse.Namespace) -> None:
    cfg = read_simple_yaml(Path(args.config))
    smtp = cfg.get("smtp", {})
    notifications = cfg.get("notifications", {})
    to_email = args.to or notifications.get("to_email") or notifications.get("default_to")
    if not to_email:
        raise RuntimeError("No recipient configured. Add notifications.to_email to config_demo.yaml or pass --to.")
    required = {
        "host": smtp.get("host"),
        "port": smtp.get("port"),
        "email": smtp.get("email"),
        "password": smtp.get("password"),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise RuntimeError(f"SMTP config missing required keys: {', '.join(missing)}")

    images = [Path(p).expanduser().resolve() for p in args.image]
    subject = args.subject or f"AIgriculture: {args.title or event_style(args.event_type)['title']}"
    style = event_style(args.event_type)
    plain_title = style["title"] if (args.title or "").strip().lower() in {"", "your field update is ready", "farm update", "aigriculture update"} else args.title
    plain = (
        f"{plain_title}\n"
        f"{args.message or style['recommendation']}\n\n"
        f"Status: {style['pill']}\n"
        f"Next step: {style['next_stage']}\n"
        "A marked farm image is attached when available.\n"
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp.get("from_email") or smtp["email"]
    msg["To"] = to_email
    msg.set_content(plain)
    cids = [make_msgid(domain="aigriculture.local")[1:-1] for _ in images]
    html_body = build_html(args, cids)
    msg.add_alternative(html_body, subtype="html")
    attach_images(msg, images, cids)

    if args.dry_run:
        preview = Path(args.preview or "farm_monitor_email_preview.html").resolve()
        preview.write_text(html_body, encoding="utf-8")
        print(f"DRY_RUN_OK preview={preview} attachments={len(images)}")
        return

    with smtplib.SMTP(smtp["host"], int(smtp.get("port", 587)), timeout=25) as server:
        server.starttls()
        server.login(smtp["email"], smtp["password"])
        server.send_message(msg)
    print(f"EMAIL_SENT attachments={len(images)}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Send a designer AIgriculture Farm Monitor detection email.")
    p.add_argument("--config", default=str(DEFAULT_CONFIG))
    p.add_argument("--to", default="")
    p.add_argument("--subject", default="")
    p.add_argument("--title", default="")
    p.add_argument("--message", default="")
    p.add_argument("--event-type", choices=["ripeness", "disease", "disease_and_ripeness", "security", "clear"], default="ripeness")
    p.add_argument("--detection-label", default="")
    p.add_argument("--confidence", type=float, default=None)
    p.add_argument("--disease-ratio", type=float, default=0.0)
    p.add_argument("--ripeness-ratio", type=float, default=0.0)
    p.add_argument("--time", default="")
    p.add_argument("--dashboard-url", default="")
    p.add_argument("--image", action="append", default=[], help="Detection image to embed and attach. Can be repeated.")
    p.add_argument("--row", dest="rows", action="append", default=[], help="Table row as 'Detected item|Status|Next stage'. Can be repeated.")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--preview", default="")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    try:
        send_email(args)
        return 0
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
