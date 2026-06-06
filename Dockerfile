FROM mcr.microsoft.com/playwright/python:v1.50.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p results

EXPOSE 8080

CMD gunicorn web_app:app --bind 0.0.0.0:${PORT:-8080} --timeout 300 --workers 1 --threads 4
