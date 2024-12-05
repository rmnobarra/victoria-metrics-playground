FROM python:3.9-slim

WORKDIR /app

# Copie os arquivos para o container
COPY . /app

# Instale as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Exponha a porta
EXPOSE 5000

# Comando de inicialização
CMD ["python", "app.py"]
