FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    python3.9 \
    python3-pip \
    poppler-utils \
    libgl1 \
    tesseract-ocr \
    tesseract-ocr-por

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt

CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
