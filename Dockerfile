# Dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Explicitly copy app.py and templates directory
COPY app.py .
COPY templates/ templates/
COPY static/ static/

EXPOSE 5000

CMD ["python", "app.py"]