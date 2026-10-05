# Dockerfile for the FastAPI backend, deployed on Render.
#
# Build: docker build -t saas-support-api -f api/Dockerfile .  (from repo root)
# Run locally: docker run -p 8000:8000 --env-file .env saas-support-api
#
# Render reads this file and builds the image automatically on every push to main.

FROM python:3.12-slim

# Install OS packages needed by psycopg (the Postgres driver).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies before copying the source code so Docker can
# cache this layer. A code change does not re-install packages.
COPY api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code.
COPY api/ ./

# Bundle the demo knowledge base so the admin "Load demo articles" button works.
COPY data/demo_kb/ /demo_kb/

# The PORT variable is set by Render; the default 8000 works locally.
ENV PORT=8000

# Start the server.
# --workers 1: one process is right for the free tier. Scale up by adding workers or replicas.
# --host 0.0.0.0: accept connections from outside the container.
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
