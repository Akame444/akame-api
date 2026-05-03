FROM python:3.11-slim

# On installe juste le nécessaire pour Python et les requêtes
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# On ignore l'avertissement root pour des logs propres
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt

COPY . .

# Plus besoin de xvfb-run ! On lance uvicorn directement.
CMD uvicorn app:app --host 0.0.0.0 --port $PORT
