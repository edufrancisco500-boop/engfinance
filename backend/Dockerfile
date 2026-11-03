FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements*.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY . .
RUN useradd --create-home appuser && mkdir -p private-media && chown appuser:appuser private-media
USER appuser
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
