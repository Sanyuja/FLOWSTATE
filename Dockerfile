FROM n8nio/n8n:latest

# FLOWSTATE additions — Python, FFmpeg, and Sharp for content processing
USER root

# System packages (Alpine Linux)
RUN apk add --no-cache \
    python3 \
    py3-pip \
    ffmpeg \
    curl

# Python packages — core FLOWSTATE deps
# content_tagger.py (open_clip_torch, torch) is intentionally excluded:
# run it on the host with GPU access. See docs/docker-setup.md.
RUN pip3 install --no-cache-dir --break-system-packages \
    anthropic \
    openai \
    pandas \
    openpyxl \
    xlsxwriter \
    pillow \
    tqdm \
    python-dotenv \
    requests

# Sharp.js — required by n8n Code nodes for image blurring (blur.js logic)
# Installed in a dedicated directory, exposed to n8n via NODE_PATH env var
RUN mkdir -p /home/node/n8n-modules && \
    cd /home/node/n8n-modules && \
    npm init -y && \
    npm install sharp

USER node
