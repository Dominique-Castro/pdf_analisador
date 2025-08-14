FROM python:3.9-slim

# Instala o Poppler (necessário para ler PDFs)
RUN apt-get update && apt-get install -y \
    poppler-utils \  # Inclui pdfinfo, pdftoppm, etc.
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt

CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
