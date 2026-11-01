FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/demo/store/

ENV PYTHONPATH=/app

EXPOSE 9000

CMD ["uvicorn", "demo.store.main:app", "--host", "0.0.0.0", "--port", "9000"]
