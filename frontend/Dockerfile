
FROM node:22-alpine

WORKDIR /app

# Copier les fichiers de dépendances
COPY package*.json ./

# Installer les dépendances
RUN npm install --include=optional

# Copier le code React
COPY . .

# Construire l'application
RUN npm run build

# Installer un serveur web léger
RUN npm install -g serve

EXPOSE 5173

# Servir l'application
CMD ["serve", "-s", "dist", "-l", "5173"]
