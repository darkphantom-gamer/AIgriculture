FROM python:3.11-slim-bookworm

# System deps: build tools for lgpio, OpenCV runtime libs
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps before copying source (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application source + bundled defaults
COPY aigriculture/      ./aigriculture/
COPY models/            ./models/
COPY labels/            ./labels/
COPY wiring.example.yaml ./wiring.example.yaml

EXPOSE 8000

CMD ["python", "-m", "aigriculture"]
