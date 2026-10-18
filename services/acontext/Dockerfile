FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn httpx
COPY app.py .
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8029"]
