"""
FLORA Intelligence — 48-hour PDF farm report builder.

Produces a themed multi-section PDF: current farm status, moisture activity,
security/intruders, plant-health & harvest, and irrigation — with a short
analysed overview. Data is read live through flora_tools' shared-state bridge
and from the on-disk Storage_Data event tree. reportlab does the layout;
matplotlib draws the moisture chart when samples exist (skipped gracefully if
not). The caller registers the file for a short-lived authenticated download.
"""
import json
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

import flora_tools  # live state via flora_tools._B; tested data tools reused

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, Image as RLImage)

# ── Theme ───────────────────────────────────────────────────────────────────────
TEAL      = colors.HexColor("#0d8a78")
TEAL_DK   = colors.HexColor("#064d4a")
MINT      = colors.HexColor("#d8f5ee")
MINT_SOFT = colors.HexColor("#f3fbf9")
INK       = colors.HexColor("#0b2e3e")
MUTE      = colors.HexColor("#5f8190")
AMBER     = colors.HexColor("#b45309")

REPORT_DIR = Path(tempfile.gettempdir()) / "flora_reports"

_TITLE = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=21,
                        textColor=TEAL_DK, leading=25, spaceAfter=2)
_SUB   = ParagraphStyle("s", fontName="Helvetica", fontSize=10,
                        textColor=MUTE, leading=14, spaceAfter=14)
_H2    = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=13,
                        textColor=TEAL_DK, leading=16, spaceBefore=16, spaceAfter=7)
_BODY  = ParagraphStyle("b", fontName="Helvetica", fontSize=10,
                        textColor=INK, leading=15, spaceAfter=5)
_NOTE  = ParagraphStyle("n", fontName="Helvetica-Oblique", fontSize=9.5,
                        textColor=MUTE, leading=14, spaceAfter=4)
_CELL  = ParagraphStyle("c", fontName="Helvetica", fontSize=9, textColor=INK, leading=12)


# ── Data gathering ──────────────────────────────────────────────────────────────

def _farm_status() -> dict:
    try:
        return json.loads(flora_tools.get_farm_status())
    except Exception:
        return {}


def _analysis() -> dict:
    try:
        return json.loads(flora_tools.analyze_farm("24h"))
    except Exception:
        return {}


def _scan_storage(window_hours: int) -> dict:
    """Walk the Storage_Data day folders for the window; classify events and
    capture their evidence image paths so the report can embed real snapshots.
    Each item is {when, label, images:[Path], ts}."""
    out = {"security": [], "disease": [], "ripeness": [], "other": []}
    root = flora_tools._B.get("STORAGE_PATH")
    if not root:
        return out
    root = Path(root)
    if not root.exists():
        return out
    cutoff = time.time() - window_hours * 3600
    now = datetime.now()
    for back in range(int(window_hours // 24) + 2):
        d = now - timedelta(days=back)
        day_dir = root / f"{d.year:04d}" / f"{d.month:02d}" / f"{d.day:02d}"
        if not day_dir.exists():
            continue
        for meta in day_dir.rglob("meta.json"):
            try:
                m = json.loads(meta.read_text(encoding="utf-8"))
            except Exception:
                continue
            raw_t = str(m.get("time") or "")
            try:
                ts = datetime.fromisoformat(raw_t.replace("Z", "")).timestamp()
            except Exception:
                ts = meta.stat().st_mtime
            if ts < cutoff:
                continue
            etype = (m.get("event_type") or "").lower()
            when = datetime.fromtimestamp(ts).strftime("%b %d  %H:%M")
            folder = meta.parent
            try:
                images = [folder / n for n in flora_tools._image_names(folder, m)]
                images = [p for p in images if p.exists()]
            except Exception:
                images = []
            if etype == "disease":
                bucket, label = "disease", (m.get("disease_best") or {}).get("label", "disease")
            elif etype == "ripeness":
                bucket, label = "ripeness", (m.get("ripeness_best") or {}).get("label", "ripeness")
            elif m.get("label"):
                bucket, label = "security", str(m.get("label"))
            else:
                bucket, label = "other", (etype or "event")
            out[bucket].append({"when": when, "label": label, "images": images, "ts": ts})
    for k in out:
        out[k].sort(key=lambda r: r["ts"], reverse=True)
    return out


def _moisture_chart_png() -> Path | None:
    """Render a moisture-trend PNG from moisture_hist; None if no data/failure."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        B = flora_tools._B
        cutoff = time.time() - 48 * 3600
        series = {}
        with B["hist_lock"]:
            for p, hist in B.get("moisture_hist", {}).items():
                pts = [(e["t"], e["v"]) for e in hist if e["t"] >= cutoff]
                if pts:
                    series[p.upper()] = pts
        if not series:
            return None
        fig, ax = plt.subplots(figsize=(7.0, 2.7), dpi=150)
        for name, pts in sorted(series.items()):
            xs = [datetime.fromtimestamp(t) for t, _ in pts]
            ys = [v for _, v in pts]
            ax.plot(xs, ys, linewidth=1.4, label=f"Plant {name}")
        ax.set_ylabel("Moisture %", fontsize=8)
        ax.set_ylim(0, 100)
        ax.tick_params(labelsize=7)
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=6, ncol=4, loc="upper center")
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        fig.tight_layout()
        out = REPORT_DIR / f"_chart_{int(time.time())}.png"
        fig.savefig(str(out))
        plt.close(fig)
        return out
    except Exception:
        return None


# ── PDF layout ──────────────────────────────────────────────────────────────────

def _decorate(canvas, doc):
    """Header band + footer drawn on every page."""
    w, h = A4
    canvas.saveState()
    canvas.setFillColor(TEAL_DK)
    canvas.rect(0, h - 16 * mm, w, 16 * mm, stroke=0, fill=1)
    canvas.setFillColor(TEAL)
    canvas.rect(0, h - 16 * mm, w, 1.6 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(18 * mm, h - 10.4 * mm, "FLORA  ·  AIgriculture")
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MINT)
    canvas.drawRightString(w - 18 * mm, h - 10.4 * mm,
                           "Farm Live Operation & Reasoning Assistant")
    canvas.setFillColor(MUTE)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(18 * mm, 11 * mm,
                      "Auto-generated by FLORA · download link expires in 5 minutes")
    canvas.drawRightString(w - 18 * mm, 11 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _kv_table(rows, col_widths):
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), MINT),
        ("TEXTCOLOR", (0, 0), (-1, 0), TEAL_DK),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, MINT_SOFT]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cfe7e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
    ]))
    return t


def _evidence_grid(records, max_items: int = 6, per_row: int = 3):
    """A grid of real evidence snapshots with time + label captions. A missing
    or unreadable image is skipped gracefully so it never breaks the report."""
    cap = ParagraphStyle("cap", fontName="Helvetica", fontSize=7.5,
                         textColor=MUTE, leading=9, alignment=1)
    tiles = []
    for rec in records:
        for img in rec.get("images", []):
            try:
                pic = RLImage(str(img), width=52 * mm, height=38 * mm, kind="proportional")
            except Exception:
                continue
            tile = Table(
                [[pic], [Paragraph(f"{rec['when']} · {rec['label']}", cap)]],
                colWidths=[54 * mm])
            tile.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))
            tiles.append(tile)
            if len(tiles) >= max_items:
                break
        if len(tiles) >= max_items:
            break
    if not tiles:
        return None
    rows = [tiles[i:i + per_row] for i in range(0, len(tiles), per_row)]
    for r in rows:
        while len(r) < per_row:
            r.append("")
    grid = Table(rows, colWidths=[58 * mm] * per_row)
    grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    return grid


def build_report(window_hours: int = 48) -> dict:
    """Build the PDF report. Returns {path, filename, pages}."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M")
    filename = f"FLORA_Farm_Report_{stamp}.pdf"
    path = REPORT_DIR / filename

    status = _farm_status()
    analysis = _analysis()
    events = _scan_storage(window_hours)
    plants = status.get("plants", {}) or {}

    story = []
    span_from = (now - timedelta(hours=window_hours)).strftime("%b %d, %H:%M")
    story.append(Paragraph(f"{window_hours}-Hour Farm Report", _TITLE))
    story.append(Paragraph(
        f"Strawberry farm · {span_from} &rarr; {now.strftime('%b %d, %H:%M')} "
        f"· generated {now.strftime('%Y-%m-%d %H:%M')}", _SUB))

    # Executive summary
    story.append(Paragraph("Overview", _H2))
    summ = status.get("summary") or "No live summary available."
    story.append(Paragraph(summ, _BODY))

    # Current farm status
    story.append(Paragraph("Current Farm Status", _H2))
    if plants:
        rows = [["Plant", "Moisture", "Sensor", "Pump"]]
        for letter, p in plants.items():
            mv = p.get("moisture_pct")
            rows.append([
                letter,
                f"{mv:.1f}%" if isinstance(mv, (int, float)) else "—",
                p.get("sensor", "?"),
                p.get("pump", "?"),
            ])
        story.append(_kv_table(rows, [70, 90, 110, 80]))
    else:
        story.append(Paragraph("No plant data available.", _NOTE))
    sec = status.get("security", {}) or {}
    fm = status.get("farm_monitor", {}) or {}
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"<b>Security:</b> guard {sec.get('guard', '?')} · "
        f"intruders: {sec.get('intruders', 'n/a')}.", _BODY))
    story.append(Paragraph(
        f"<b>FarmMonitor:</b> {fm.get('plant_health_and_harvest', 'no scan result')} "
        f"(camera {'online' if fm.get('camera_online') else 'offline'}).", _BODY))

    # Moisture activity
    story.append(Paragraph("Moisture Activity", _H2))
    chart = _moisture_chart_png()
    trend = analysis.get("moisture_trend")
    if isinstance(trend, dict) and trend:
        rows = [["Plant", "Avg %", "Min %", "Max %", "Samples"]]
        for letter, t in sorted(trend.items()):
            rows.append([letter, t.get("avg", "—"), t.get("min", "—"),
                         t.get("max", "—"), t.get("samples", 0)])
        story.append(_kv_table(rows, [70, 80, 80, 80, 80]))
    else:
        story.append(Paragraph(
            "No moisture samples were recorded in this window — the sensor "
            "network appears offline. Check wiring, power and the I²C bus.",
            _NOTE))
    if chart:
        story.append(Spacer(1, 8))
        story.append(RLImage(str(chart), width=170 * mm, height=65 * mm))

    # Security & intruders
    story.append(Paragraph("Security &amp; Intruders", _H2))
    si = events["security"]
    if si:
        story.append(Paragraph(
            f"{len(si)} security detection(s) in the last {window_hours}h.", _BODY))
        rows = [["Time", "Detected"]] + [[r["when"], r["label"]] for r in si[:14]]
        story.append(_kv_table(rows, [150, 270]))
        grid = _evidence_grid(si, max_items=6)
        if grid is not None:
            story.append(Spacer(1, 7))
            story.append(Paragraph("Captured snapshots", _NOTE))
            story.append(grid)
    else:
        story.append(Paragraph(
            "No intruders or security events detected — the farm stayed secure.",
            _NOTE))

    # Plant health & harvest
    story.append(Paragraph("Plant Health &amp; Harvest", _H2))
    dis, rip = events["disease"], events["ripeness"]
    if dis or rip:
        story.append(Paragraph(
            f"{len(dis)} disease alert(s) and {len(rip)} ripeness/harvest "
            f"detection(s) from the FarmMonitor camera.", _BODY))
        rows = [["Time", "Type", "Finding"]]
        for r in dis[:8]:
            rows.append([r["when"], "Disease", r["label"]])
        for r in rip[:8]:
            rows.append([r["when"], "Harvest", r["label"]])
        story.append(_kv_table(rows, [130, 90, 200]))
        grid = _evidence_grid(dis + rip, max_items=6)
        if grid is not None:
            story.append(Spacer(1, 7))
            story.append(Paragraph("Captured snapshots", _NOTE))
            story.append(grid)
    else:
        story.append(Paragraph(
            "No disease or harvest events were logged by the FarmMonitor camera "
            "in this window.", _NOTE))

    # Irrigation
    story.append(Paragraph("Irrigation Activity", _H2))
    irr = analysis.get("irrigation_events")
    if isinstance(irr, dict) and irr:
        rows = [["Plant", "Burst events (24h)"]]
        for letter, n in sorted(irr.items()):
            rows.append([letter, n])
        story.append(_kv_table(rows, [120, 200]))
    else:
        story.append(Paragraph(
            "No automatic irrigation bursts ran — with sensors offline the burst "
            "system stayed idle. Auto-irrigation is "
            f"{status.get('auto_irrigation', 'unknown')}.", _NOTE))

    story.append(Spacer(1, 18))
    story.append(Paragraph(
        "FLORA watches over this farm continuously. Bring the sensors online and "
        "the next report will be rich with moisture trends and irrigation history. "
        "\U0001f33f", _NOTE))

    doc = SimpleDocTemplate(
        str(path), pagesize=A4, topMargin=24 * mm, bottomMargin=20 * mm,
        leftMargin=18 * mm, rightMargin=18 * mm,
        title=f"FLORA {window_hours}h Farm Report", author="FLORA Intelligence")
    doc.build(story, onFirstPage=_decorate, onLaterPages=_decorate)

    if chart:
        try:
            chart.unlink()
        except Exception:
            pass

    return {"path": str(path), "filename": filename, "pages": getattr(doc, "page", 1)}
