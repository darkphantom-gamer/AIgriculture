# AIgriculture — production image.
# Pinned to Python 3.13 to match the Pi's native interpreter (Bookworm ships 3.13).
# Multi-arch: builds clean for linux/arm64 (Pi 5) AND linux/amd64 (laptops).

FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ── System packages ──────────────────────────────────────────────────────
# Runtime libs:
#   - libgl1 / libglib2.0-0  → opencv
#   - libgpiod2              → lets lgpio find a chip on hosts wired through /dev/gpiochip*
#   - mariadb-client         → handy for `docker compose exec` debugging
#   - tini                   → clean PID 1 / signal handling
# Build tools (needed to build the `lgpio` Python wheel from source on slim images):
#   - gcc / g++ / make / swig / python3-dev
# We remove build tools at the end of the same layer to keep the image small.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libgpiod2 mariadb-client tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first so this layer caches.
# `lgpio` is deliberately NOT in requirements.txt (see comment there) — it
# only matters on a real Pi and would force a from-source build here.
COPY requirements.txt ./
RUN pip install -r requirements.txt \
    && rm -rf /root/.cache/pip

# Copy application code.
COPY plantwatch.py \
     dashboard_sample.html \
     login.html \
     farm_monitor_designer_email.py \
     farm_monitor_pt_scan.py \
     farm_monitor_disease_labels.json \
     farm_monitor_ripeness_labels.json \
     flora_agent.py flora_config.py flora_report.py flora_scheduler.py flora_tools.py \
     meshtastic_flora_bridge.py \
     agrisense-favicon.svg farmer.png test_drive_avatar.png low-cortisol.png threat.mp3 \
     wiring.example.yaml \
     ./

# Pre-create runtime + storage dirs with a non-root user.
RUN useradd --create-home --shell /bin/bash farm \
    && mkdir -p /app/Storage_Data /app/runtime /app/FarmMonitor_Work \
    && chown -R farm:farm /app

USER farm

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "plantwatch.py"]
