# Python bazaviy image
FROM python:3.10-slim

# Workdir ichiga o‘tamiz
WORKDIR /app

# System dependencies (psycopg2 va boshqalar uchun)
RUN apt-get update \
    && apt-get install -y gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt ni ko‘chirib o‘rnatamiz
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Barcha project fayllarini ko‘chirib olamiz
COPY . .

# Django ishlatish uchun port
EXPOSE 8000

# Default command (celery va beat uchun docker-compose alohida override qiladi)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
