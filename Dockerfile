FROM python:3.9-slim

# 1. Primeiro atualiza os repositórios com tratamento de erro
RUN apt-get update -qq --fix-missing && \
    apt-get install -y --no-install-recommends \
    wget \
    && rm -rf /var/lib/apt/lists/*

# 2. Adiciona repositório do Tesseract OCR
RUN wget -O /etc/apt/trusted.gpg.d/tesseract-ocr-debian.asc https://notesalexp.org/debian/alexp_key.asc && \
    echo "deb http://notesalexp.org/tesseract-ocr5/$(lsb_release -cs)/ $(lsb_release -cs) main" > /etc/apt/sources.list.d/tesseract-ocr.list

# 3. Instala todas as dependências em um único RUN
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
    poppler-utils \
    libgl1-mesa-glx \
    tesseract-ocr \
    tesseract-ocr-por \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 4. Configura o ambiente
WORKDIR /app

# 5. Instala dependências Python primeiro para melhor cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copia o restante dos arquivos
COPY . .

# 7. Configura variáveis de ambiente
ENV TESSERACT_CMD=/usr/bin/tesseract
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
