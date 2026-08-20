FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for layer caching
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code. api/ lands at /app, so imports stay flat.
COPY api/ .

# Data files: seed farms and the crop calendar are read at runtime.
# routers/internal.py resolves /app/data/seed/demo_farms.json here.
COPY data/ /app/data/

# Baselines are read by main.py at startup from rules/baselines.json
COPY api/rules/baselines.json /app/rules/baselines.json

# Fail fast rather than at 2am: prove the seed file made it into the image.
RUN test -f /app/data/seed/demo_farms.json \
    && test -f /app/data/crop_calendar.csv \
    && echo "data files present"

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
