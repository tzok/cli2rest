FROM python:3-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends tini && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app
COPY app.py .

EXPOSE 8000

ENTRYPOINT ["tini", "--"]

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

HEALTHCHECK --start-period=30s --start-interval=1s CMD python -c "import requests; requests.get('http://localhost:8000/health').raise_for_status()"
