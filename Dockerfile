FROM python:3.9-slim

# 1. Instala dependências do sistema de forma otimizada
RUN apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
    poppler-utils \
    libgl1-mesa-glx \
    tesseract-ocr \
    tesseract-ocr-por \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 2. Configura ambiente Python
WORKDIR /app

# 3. Instala dependências Python primeiro (cache mais eficiente)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copia o resto dos arquivos
COPY . .

# 5. Configura variáveis de ambiente para o Tesseract
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata

# 6. Comando de execução
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
