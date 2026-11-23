
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copier le code du backend
COPY app/ ./app/
COPY scripts/ ./scripts/

# Dossier de stockage ChromaDB et des documents
RUN mkdir -p /app/chroma_db /app/data

EXPOSE 9501

# Lancer l'API FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9501"]
