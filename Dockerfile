# Imagem base leve do Python 3.9
FROM python:3.9-slim

# Diretório de trabalho no container
WORKDIR /app

# Copia tudo para o container
COPY . .

# Instala dependências (certifique-se de ter requirements.txt!)
RUN pip install --no-cache-dir -r requirements.txt

# Comando para rodar o app
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
