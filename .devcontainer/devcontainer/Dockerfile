FROM python:3.9

RUN apt-get update && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    libgl1-mesa-glx

WORKDIR /workspace
COPY . .
