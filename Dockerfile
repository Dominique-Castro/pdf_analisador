FROM python:3.9-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    poppler-utils \
    libgl1-mesa-glx \
    tesseract-ocr \
    tesseract-ocr-por && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
