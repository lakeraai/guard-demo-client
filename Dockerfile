# ============================
# Stage 1 — Python Builder
# ============================
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv

# System deps for building Python wheels
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        build-essential \
        python3-dev && \
    python -m venv $VIRTUAL_ENV && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Clone frontend repo
RUN git clone --depth 1 https://github.com/vmummer/guard-demo-client /home/lakeraai && \
    rm -rf /home/lakeraai/.git


# ============================
# Stage 2 — Final Runtime Image
# ============================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    NODE_MAJOR=20 \
    BROWSERSLIST_UPDATE_DB=0

WORKDIR /home/lakeraai

# Create non-root user
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -m -s /usr/sbin/nologin lakeraai-user

# Install Node.js (clean, multi-arch safe)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates gnupg && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
      | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" \
      > /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get purge -y --auto-remove gnupg curl && \
    rm -rf /var/lib/apt/lists/*

# Copy Python venv + frontend code from builder
COPY --from=builder --chown=lakeraai-user:appuser $VIRTUAL_ENV $VIRTUAL_ENV
COPY --from=builder --chown=lakeraai-user:appuser /home/lakeraai /home/lakeraai

# Copy backend code
COPY --chown=lakeraai-user:appuser . .

# Install frontend deps at build time (NOT runtime)
#RUN npm ci --omit=dev || npm install --omit=dev

RUN npm ci  || npm install || npm run build 

# Fix permissions for non-root user

RUN  mkdir -p /home/lakeraai/chroma && \
     mkdir -p /home/lakeraai/backend/data/chroma && \
     mkdir -p /home/lakeraai/data/chroma && \
     chown -R lakeraai-user:appuser /home/lakeraai && \
     chmod -R g+w /home/lakeraai

USER lakeraai-user

EXPOSE 8000

CMD ["python", "start_all.py"]
