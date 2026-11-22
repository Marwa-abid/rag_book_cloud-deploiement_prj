# RAG Book

Application de questions-réponses sur un livre PDF avec FastAPI, ChromaDB,
sentence-transformers et OpenAI, Ollama ou Gemini. Les réponses s'appuient
exclusivement sur le contenu retrouvé et sont générées dans la langue de la question.

## Prérequis

- Python 3.11
- Une clé API pour OpenAI (`LLM_PROVIDER=openai`) ou Gemini
  (`LLM_PROVIDER=gemini`), ou un serveur Ollama local
  (`LLM_PROVIDER=ollama`)
- Un fichier PDF à placer dans `backend/data/`

## Installation (PowerShell)

```powershell
cd rag-book\backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Configurez `LLM_PROVIDER`, `LLM_MODEL` et, pour OpenAI ou Gemini, `LLM_API_KEY`
dans `backend/.env`. Pour Gemini, choisissez par exemple `LLM_PROVIDER=gemini`
et un modèle Gemini pris en charge par votre API key. Ollama n'utilise pas de clé.
La température du modèle se règle avec `LLM_TEMPERATURE` (défaut : `0.2`).
Les origines CORS se configurent avec `CORS_ORIGINS`, séparées par des virgules
(défaut : `http://localhost:5173,http://localhost:3000`).
Le PDF utilisé pour l'indexation et le lecteur est défini par `BOOK_PATH`
(défaut : `data/livre.pdf`, relatif à `backend`). Copiez le livre à cet endroit
ou indiquez un chemin différent dans `backend/.env`.

## Indexation

Depuis `rag-book\backend`, avec l'environnement virtuel activé :

```powershell
.\.venv\Scripts\python.exe scripts\index_book.py "data\livre.pdf"
```

L'index persistant est enregistré dans `backend/chroma_db/`.

## Questions en ligne de commande

Depuis `rag-book\backend`, une question en argument :

```powershell
.\.venv\Scripts\python.exe scripts\ask_cli.py "What does the book say about time management?"
```

Sans argument, le script démarre une session interactive. Les questions peuvent
être posées en français ou en anglais; tapez `quit` pour quitter.

Pour inspecter le PDF et afficher cinq chunks aléatoires sans créer d'index :

```powershell
.\.venv\Scripts\python.exe -m scripts.inspect_chunks "data\livre.pdf"
```

## Frontend React

Prérequis : Node.js 20.19 ou plus récent. Depuis la racine du dépôt :

```powershell
Set-Location .\rag-book\frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Le frontend est accessible à `http://localhost:5173`. Configurez `VITE_API_URL`
dans `.env` si l'API backend n'est pas à `http://localhost:8000`.
Le bouton « Le livre » ouvre le PDF dans un panneau latéral. Les citations et
les pages des sources permettent d'accéder directement à la page correspondante.
L'historique des conversations s'ouvre depuis l'icône de panneau dans l'en-tête.
Les conversations, leurs sources et leur date sont conservées dans le stockage
local du navigateur après chaque réponse; elles ne sont pas envoyées au backend
en dehors de l'historique des dix derniers messages d'une question. Le panneau
permet de rechercher, renommer, supprimer ou effacer ces conversations. Le titre
est créé à partir de la première question et l'historique est limité aux
50 conversations les plus récentes. Une réponse partielle est conservée si sa
génération est arrêtée ou si l'utilisateur change de conversation. Les données
peuvent être effacées depuis « Tout effacer »; elles restent propres au navigateur.
En cas d'indisponibilité ou de saturation du stockage local, l'interface affiche
un avertissement au lieu d'interrompre le chat.

Tests et build de production :

```powershell
npm test
npm run build
```

## Démarrage du backend

```powershell
Set-Location ..\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

L'API est disponible à `http://127.0.0.1:8000`. Les routes comprennent
`GET /api/health`, `POST /api/chat`, `POST /api/chat/stream`,
`GET /api/book` et `GET /api/book/info`. La route du livre prend en charge les
requêtes HTTP Range pour la lecture PDF intégrée.
La documentation interactive est à `http://127.0.0.1:8000/docs`.

Exemple :

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/chat `
  -ContentType "application/json" `
  -Body '{"question":"Quels conseils le livre donne-t-il sur la gestion du temps ?","history":[]}'
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Docker n'est pas inclus à ce stade.
