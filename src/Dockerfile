# Dockerfile
FROM python:3.11

# Ishchi papka
WORKDIR /app

# requirements.txt ni copy qilamiz
COPY requirements.txt .

# Kutubxonalarni install qilamiz
RUN pip install --no-cache-dir -r requirements.txt

# Projectni copy qilamiz
COPY . .

# Django runserver (dev uchun)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
