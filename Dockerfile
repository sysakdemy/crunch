# Dockerfile pour l'application Crunch
FROM python:3.11-slim

# Métadonnées
LABEL maintainer="crunch-app"
LABEL description="Application web pour tester l'autoscaling Kubernetes"

# Variables d'environnement
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=5000
ENV HOST=0.0.0.0

# Installer les dépendances système
RUN apt-get update && apt-get install -y \
    bc \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Créer un utilisateur non-root pour la sécurité
RUN groupadd -r crunch && useradd -r -g crunch crunch

# Créer le répertoire de travail
WORKDIR /app

# Copier et installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code de l'application
COPY crunch_web.py .

# Changer les permissions
RUN chown -R crunch:crunch /app

# Basculer vers l'utilisateur non-root
USER crunch

# Exposer le port
EXPOSE 5000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/health')" || exit 1

# Commande par défaut
CMD ["python", "crunch_web.py"]