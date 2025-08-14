FROM python:3.9-slim

# 1. Instala Poppler e dependências do sistema
RUN apt-get update && apt-get install -y \
    poppler-utils \       # Ferramentas para manipulação de PDF (pdfinfo, pdftoppm)
    libgl1 \              # Necessário para renderização gráfica (ex: pdf2image)
    && rm -rf /var/lib/apt/lists/*  # Limpa cache para reduzir tamanho da imagem

# 2. Configura o ambiente
WORKDIR /app
COPY . .

# 3. Instala dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# 4. Comando para iniciar o app
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
