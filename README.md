# Lunar Hack Madagascar - Monorepo

Ce depot regroupe plusieurs prototypes de la solution Lunar Hack (axes, backend/frontend, SEO), avec des stacks Python + React et des integrations IA locales (Ollama, RAGFlow).

## Contenu du depot

- `axis_1_LUNAR HACK/lunar-hack/`
  - Version Axe 1 (backend FastAPI, consumers, producer, frontend React, docker-compose, docs N8N).
- `axis2_Lunar_Hack/`
  - Version Axe 2 (moteur de decision IA, orchestration multi-agent, RAGFlow, frontend TypeScript).
- `lunar-combined/`
  - Frontend combine pour integration des vues et parcours.
- `SEO/`
  - Module SEO (backend Python + frontend React) et scripts associes.

## Prerequis

- Python 3.10+
- Node.js 18+
- npm
- Git
- Optionnel selon les modules IA:
  - Ollama en local
  - RAGFlow en local

## Demarrage rapide

## 1) Axe 2 (recommande pour la demo decision IA)

Backend:

```powershell
cd axis2_Lunar_Hack\backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```powershell
cd axis2_Lunar_Hack\frontend
npm install
npm run dev
```

## 2) Axe 1

Frontend:

```powershell
cd "axis_1_LUNAR HACK\lunar-hack\frontend"
npm install
npm run dev
```

Backend:

```powershell
cd "axis_1_LUNAR HACK\lunar-hack\backend"
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 3) Module SEO

Frontend:

```powershell
cd SEO\frontend
npm install
npm run dev
```

Backend:

```powershell
cd SEO
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## RAG (Axe 2)

Pour indexer les documents de reference dans RAGFlow:

```powershell
cd axis2_Lunar_Hack\backend
python scripts/rag_indexer.py --docs-dir ..\data\sample_docs --base-url http://localhost:9380 --dataset-id sales-kb --create-dataset --embedding-model bge-m3 --verbose
```

## Notes importantes

- Le port backend par defaut est souvent `8000`. Verifier qu'un seul backend ecoute ce port a la fois.
- Plusieurs sous-projets ont leur propre `package.json` et/ou `requirements.txt`.
- Le fichier `.gitignore` racine est configure pour ignorer les artefacts Python/Node courants.

## Contribution

1. Creer une branche de travail.
2. Commiter par module (`axis2`, `axis1`, `seo`, etc.).
3. Ouvrir une pull request avec description des changements et instructions de test.

## Licence

Projet academique/hackathon. Ajouter la licence officielle du projet si necessaire.
