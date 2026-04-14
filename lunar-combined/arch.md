# Architecture generale - Sa3ed Combined

## 1. Objectif
Ce document decrit l'architecture generale du frontend "combined" (Sa3ed) et l'architecture fonctionnelle de chaque tab.

Le projet centralise plusieurs experiences produit dans une seule application React:
- Dashboard KPI en temps reel
- Analyse multi-agents
- Chat Axis 2
- Test Pillar 3 (quality chat)
- SEO Agent

## 2. Vue d'ensemble

### 2.1 Architecture applicative
- Framework UI: React
- Routing: react-router-dom
- Build/dev server: Vite
- Organisation: composants par tab, styles CSS separes
- Etat: useState/useEffect/useMemo/useCallback (pas de store global)

### 2.2 Composition de l'application
- Entree: frontend/src/main.jsx
- Navigation globale: frontend/src/NavBar.jsx
- Pages (routes):
  - / -> frontend/src/App.jsx (Dashboard)
  - /agents -> frontend/src/AgentAnalysis.jsx
  - /axis2-chat -> frontend/src/Axis2ChatTab.jsx
  - /pillar3-test -> frontend/src/Pillar3QualityTab.jsx
  - /seo-agent -> frontend/src/SeoTab.jsx

### 2.3 Flux global
1. L'utilisateur navigue via la navbar.
2. Chaque tab charge ses donnees depuis son backend cible.
3. Les reponses sont rendues localement dans le composant du tab.
4. Les erreurs reseau sont affichees dans le tab concerne.

## 3. Architecture technique du combined

### 3.1 Routing et shell
- main.jsx monte BrowserRouter et les routes.
- NavBar est persistante et commune a toutes les pages.
- Chaque tab est une page autonome avec sa propre logique reseau et son propre style.

### 3.2 Configuration reseau (env)
Variables principales utilisees:
- VITE_API_BASE (Dashboard + Agents, fallback local)
- VITE_WS_URL (WebSocket KPI)
- VITE_AXIS2_API_BASE_URL (Axis 2)
- VITE_SEO_API_BASE_URL (SEO)
- VITE_PILLAR3_API_BASE_URL (Pillar 3, optionnel)
- VITE_PILLAR3_WORKSPACE_ID (Pillar 3, optionnel)

Proxy dev Vite:
- /pillar3-api -> http://127.0.0.1:8003

But: eviter les problemes CORS pendant le developpement local pour Pillar 3.

### 3.3 Style et isolation UI
- Chaque tab a son fichier CSS dedie.
- Les classes CSS sont prefixees par domaine de tab pour limiter les collisions.
- Le design system est "lightly shared" mais chaque tab garde sa personnalite visuelle.

## 4. Architecture par tab

## 4.1 Tab Dashboard (/)
Fichier: frontend/src/App.jsx

Responsabilite:
- Afficher les KPI business en temps reel.
- Offrir des filtres (produit, client, type de panier).
- Afficher tendances, distributions, insights.
- Lancer un module "Smart Recommendations".

Entrees reseau:
- GET /api/kpis
- WebSocket /ws/kpis
- GET /api/smart-recommendations/last
- POST /api/smart-recommendations

Sorties UI:
- Cards KPI
- Graphes (line chart + bar chart)
- Tableaux d'analyse
- Recommandations business/marketing (panneau dedie)

## 4.2 Tab Agents IA (/agents)
Fichier: frontend/src/AgentAnalysis.jsx

Responsabilite:
- Piloter une execution multi-agents orientee operations.
- Afficher le resultat par sous-onglets internes:
  - Analyst
  - Emails
  - Research
  - Business & Marketing

Entrees reseau:
- GET /api/agent-analysis/last
- POST /api/agent-analysis

Sorties UI:
- Banniere de statut (running/done/error)
- Resume executif et niveau de risque
- Emails cibles (high value/churn)
- Facteurs externes et correlations
- Recommandations actionnables

## 4.3 Tab Axis 2 Chat (/axis2-chat)
Fichiers:
- frontend/src/Axis2ChatTab.jsx
- frontend/src/axis2Api.js

Responsabilite:
- Fournir une experience conversationnelle Axis 2 multilingue.
- Gerer sessions, historique, messages, follow-up.
- Afficher les sources RAG quand presentes.

Entrees reseau:
- POST /chat
- GET /sessions/{user_id}
- GET /sessions/{user_id}/{session_id}/messages

Caracteristiques:
- user_id persiste en localStorage
- session_id gere cote front
- support en/fr/ar
- rendu des chips de sources (rag_sources)

## 4.4 Tab Pillar 3 Test (/pillar3-test)
Fichier: frontend/src/Pillar3QualityTab.jsx

Responsabilite:
- Offrir un front de test rapide pour le chat marketing Pillar 3.
- Envoyer message + images optionnelles au backend.
- Afficher assistant_message + clarifying_questions.

Entree reseau:
- POST /v1/marketing/chat

Details d'integration:
- Base API par defaut: /pillar3-api (proxy Vite -> 127.0.0.1:8003)
- workspace_id non expose dans l'UI (interne via env/fallback)
- Preparation locale des images:
  - lecture dimensions
  - conversion base64
  - envoi metadata + contenu

## 4.5 Tab SEO Agent (/seo-agent)
Fichier: frontend/src/SeoTab.jsx

Responsabilite:
- Construire un brief SEO.
- Appeler le service SEO.
- Presenter la strategie (keywords, clusters, actions 30 jours).

Entree reseau:
- POST /api/seo/recommend

Sorties UI:
- Resume business
- Tableau des keywords recommandes
- Recommandations on-page
- Plan d'action SEO

## 5. Front-back mapping

- Dashboard + Agents: backend KPI/analytics principal
- Axis 2 Chat: backend Axis 2 decision engine
- Pillar 3 Test: backend Hackaton_3 marketing chat
- SEO Agent: backend SEO dedie

Ce choix permet de garder un "frontend hub" unique qui orchestre plusieurs backends specialises.

## 6. Decisions d'architecture

1. Multi-tabs plutot que multi-apps
- Navigation unifiee pour demo et exploitation.

2. Isolation forte par tab
- Chaque tab garde son contrat API et sa logique metier.

3. Integration progressive
- Le combined peut ajouter de nouveaux tabs sans casser l'existant.

4. Proxy dev pour Pillar 3
- Simplifie les tests locaux et limite les problemes CORS.

## 7. Lancement local (resume)

Depuis lunar-combined/frontend:
1. npm install
2. npm run dev

Pre-requis:
- Les backends cibles doivent etre disponibles sur leurs URLs respectives.
- Pour Pillar 3, demarrer backend sur 127.0.0.1:8003 si usage du proxy par defaut.

## 8. Evolution recommandee

- Centraliser les clients API dans des modules dedies par domaine.
- Ajouter un mecanisme de health checks multi-backend dans le shell global.
- Ajouter un observability panel (latence, erreurs, statut de connectivite) par tab.
