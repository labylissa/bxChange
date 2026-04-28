# bxChange — Legacy Connector Platform
## Fichier de contexte permanent pour Claude Code

---

## 🎯 Vision du Projet

bxChange est une plateforme SaaS B2B qui connecte des systèmes legacy (SOAP/WSDL, XML, APIs hétérogènes) à des applications modernes en exposant des endpoints REST/JSON propres, sécurisés et documentés.

**Slogan :** *Le pont entre 30 ans de legacy et les apps de demain.*

---

## 🗂️ Structure du Repository

```
bxChange/
├── CLAUDE.md                  ← CE FICHIER (racine du projet)
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example
├── .github/
│   └── workflows/
│       ├── ci.yml             ← lint + test à chaque push
│       └── deploy.yml         ← deploy staging/prod
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   ├── app/
│   │   ├── main.py            ← point d'entrée FastAPI
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── auth.py
│   │   │       ├── connectors.py
│   │   │       ├── executions.py
│   │   │       ├── logs.py
│   │   │       └── api_keys.py
│   │   ├── core/
│   │   │   ├── config.py      ← Settings Pydantic BaseSettings
│   │   │   ├── security.py    ← JWT, hashing, chiffrement
│   │   │   └── dependencies.py← get_db, get_current_user
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── connector.py
│   │   │   ├── execution.py
│   │   │   ├── api_key.py
│   │   │   └── subscription.py
│   │   ├── schemas/
│   │   │   ├── user.py
│   │   │   ├── connector.py
│   │   │   ├── execution.py
│   │   │   └── api_key.py
│   │   ├── services/
│   │   │   ├── soap_engine.py  ← zeep, parsing WSDL, appels SOAP
│   │   │   ├── rest_engine.py  ← httpx async, auth, retry
│   │   │   ├── transformer.py  ← XML→JSON, mapping, nettoyage
│   │   │   └── crypto.py       ← AES-256 chiffrement credentials
│   │   ├── workers/
│   │   │   ├── celery_app.py
│   │   │   └── tasks.py
│   │   └── db/
│   │       ├── session.py      ← AsyncSession SQLAlchemy
│   │       └── base.py
│   └── tests/
│       ├── conftest.py
│       ├── test_auth.py
│       ├── test_soap_engine.py
│       ├── test_rest_engine.py
│       └── test_transformer.py
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── features/
│       │   ├── auth/
│       │   ├── connectors/
│       │   ├── logs/
│       │   └── billing/
│       ├── components/
│       │   └── ui/
│       ├── lib/
│       │   └── api/
│       └── stores/
└── nginx/
    └── nginx.conf
```

---

## 🛠️ Stack Technique

### Backend
| Technologie | Version | Usage |
|-------------|---------|-------|
| Python | 3.11+ | Runtime |
| FastAPI | 0.110+ | Framework API |
| SQLAlchemy | 2.x (async) | ORM |
| PostgreSQL | 15 | Base de données |
| Alembic | latest | Migrations |
| Pydantic | v2 | Validation |
| zeep | latest | Client SOAP |
| httpx | latest | Client HTTP async |
| xmltodict | latest | Parsing XML→dict |
| python-jose | latest | JWT |
| passlib[bcrypt] | latest | Hashing passwords |
| cryptography | latest | AES-256 |
| Celery | 5.x | Workers async |
| Redis | 7 | Cache + broker Celery |

### Frontend
| Technologie | Version | Usage |
|-------------|---------|-------|
| React | 18 | UI framework |
| TypeScript | 5.x | Typage strict |
| Vite | 5.x | Build tool |
| TailwindCSS | 3.x | Styling |
| React Router | v6 | Routing |
| React Query | v5 | Data fetching + cache |
| Zustand | latest | State management |
| Axios | latest | HTTP client |
| Recharts | latest | Graphiques dashboard |
| Zod | latest | Validation schemas |

### Infra
- Docker + Docker Compose (dev)
- Nginx (reverse proxy, SSL)
- GitHub Actions (CI/CD)

---

## 📐 Conventions de Code

### Python / Backend
- **Style :** PEP 8, Black formatter, isort pour les imports
- **Typage :** Type hints obligatoires sur toutes les fonctions
- **Async :** Préférer `async def` pour toutes les routes et services
- **Nommage :**
  - Classes : `PascalCase`
  - Fonctions/variables : `snake_case`
  - Constantes : `UPPER_SNAKE_CASE`
  - Fichiers : `snake_case.py`
- **Modèles SQLAlchemy :** héritent de `Base` (declarative), colonnes avec type explicite
- **Schémas Pydantic :** `XxxCreate`, `XxxRead`, `XxxUpdate` pour chaque entité
- **Routes FastAPI :** préfixe `/api/v1/`, tags pour la doc Swagger
- **Gestion erreurs :** `HTTPException` avec codes HTTP sémantiques
- **Ne jamais** logger les credentials, tokens ou payloads sensibles

### TypeScript / Frontend
- **Style :** ESLint + Prettier
- **Typage :** `strict: true` dans tsconfig, pas de `any`
- **Composants :** Functional components uniquement, pas de class components
- **Nommage :**
  - Composants : `PascalCase.tsx`
  - Hooks : `useXxx.ts`
  - Stores : `useXxxStore.ts`
  - Utils : `camelCase.ts`
- **Imports :** alias `@/` pour `src/`
- **API calls :** toujours via React Query (pas de fetch direct dans les composants)

---

## 🔐 Sécurité — Règles Absolues

1. **Credentials connecteurs :** toujours chiffrés AES-256 avant stockage (via `services/crypto.py`)
2. **Mots de passe :** uniquement stockés en bcrypt hash, jamais en clair
3. **JWT :** access token 15 min, refresh token 7 jours avec rotation
4. **API Keys :** stockées en SHA-256 hash uniquement, affichées une seule fois à la création
5. **Logs :** ne jamais inclure `auth_config`, `hashed_password`, tokens dans les logs
6. **CORS :** origins explicites uniquement (pas de wildcard `*` en prod)
7. **Rate limiting :** via Redis sur les endpoints `/execute` et `/auth`
8. **Variables d'env :** jamais hardcodées, toujours via `.env` / `Settings`

---

## 🗄️ Schéma Base de Données

### Tables principales

```sql
-- users
id UUID PK | email VARCHAR UNIQUE | hashed_password VARCHAR
full_name VARCHAR | tenant_id UUID FK | role ENUM(admin,developer,viewer)
is_active BOOLEAN | created_at TIMESTAMP | last_login_at TIMESTAMP

-- tenants
id UUID PK | name VARCHAR | slug VARCHAR UNIQUE
created_at TIMESTAMP

-- connectors
id UUID PK | tenant_id UUID FK | name VARCHAR | type ENUM(soap,rest)
base_url TEXT | wsdl_url TEXT | auth_type ENUM(none,basic,bearer,apikey,oauth2)
auth_config JSONB (chiffré AES-256) | headers JSONB | transform_config JSONB
status ENUM(active,error,disabled,draft) | created_by UUID FK | created_at TIMESTAMP

-- executions
id UUID PK | connector_id UUID FK | status ENUM(success,error,timeout,pending)
duration_ms INTEGER | request_payload JSONB | response_payload JSONB
error_message TEXT | http_status INTEGER
triggered_by ENUM(api_key,dashboard,scheduled) | created_at TIMESTAMP

-- api_keys
id UUID PK | tenant_id UUID FK | key_hash VARCHAR
name VARCHAR | permissions JSONB | rate_limit INTEGER
expires_at TIMESTAMP | is_active BOOLEAN | created_at TIMESTAMP

-- subscriptions
id UUID PK | tenant_id UUID FK | plan ENUM(starter,professional,enterprise)
stripe_sub_id VARCHAR | status ENUM(active,past_due,cancelled,trialing)
connector_limit INTEGER | calls_limit_month INTEGER | current_period_end TIMESTAMP
```

---

## 🔌 API Endpoints

### Auth
```
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
GET    /api/v1/auth/me
POST   /api/v1/auth/logout
```

### Connectors
```
GET    /api/v1/connectors              ← liste (tenant courant)
POST   /api/v1/connectors              ← créer connecteur
GET    /api/v1/connectors/{id}         ← détail
PUT    /api/v1/connectors/{id}         ← modifier
DELETE /api/v1/connectors/{id}         ← supprimer
POST   /api/v1/connectors/{id}/execute ← exécuter le connecteur
POST   /api/v1/connectors/{id}/test    ← test sans log
GET    /api/v1/connectors/{id}/schema  ← JSON schema de sortie
```

### Executions / Logs
```
GET    /api/v1/executions              ← liste avec filtres
GET    /api/v1/executions/{id}         ← détail exécution
GET    /api/v1/logs/metrics            ← métriques dashboard
```

### API Keys
```
GET    /api/v1/api-keys                ← liste
POST   /api/v1/api-keys                ← créer (retourne la clé en clair une fois)
DELETE /api/v1/api-keys/{id}           ← révoquer
```

---

## 🚀 Roadmap & Sprints

### Phase 1 — MVP (Sprints 1–8) ← EN COURS
| Sprint | Objectif | Statut |
|--------|----------|--------|
| S1 | Setup Docker + FastAPI + PostgreSQL + Redis + Alembic | ✅ Done |
| S2 | Auth JWT complet (register, login, refresh, me) | ✅ Done |
| S3 | SOAP Engine (zeep, WSDL parsing, appel, XML brut) | ✅ Done |
| S4 | REST Engine (httpx async, tous types auth) | ✅ Done |
| S5 | JSON Transformer (XML→JSON, mapping, nettoyage) | ✅ Done |
| S6 | CRUD Connecteurs + chiffrement + endpoint /execute | ✅ Done |
| S7 | Logs & Exécutions (table + API) | ✅ Done |
| S8 | API Keys (génération, validation, rate limiting) | ✅ Done |

### Phase 2 — Dashboard (Sprints 9–11)
| Sprint | Objectif | Statut |
|--------|----------|--------|
| S9 | Frontend React : Auth + Layout + Routing | ✅ Done |
| S10 | Frontend : Wizard connecteur + page test | ✅ Done |
| S11 | Frontend : Dashboard métriques + Logs viewer | ✅ Done |

### Phase 3 — Sécurité (Sprint 12–14)
- OAuth2, mTLS, 2FA, Row-Level Security, Audit logs

### Phase 4 — SaaS Commercial (Sprint 15–17)
- Billing Stripe, Self-service onboarding, White label

### Phase 5 — IA (Sprint 18+)
- Mapping XML→JSON automatique par LLM

---

## ⚡ Commandes Utiles

```bash
# Démarrer tout l'environnement local
docker-compose up -d

# Logs backend
docker-compose logs -f backend

# Nouvelle migration Alembic
docker-compose exec backend alembic revision --autogenerate -m "description"

# Appliquer les migrations
docker-compose exec backend alembic upgrade head

# Lancer les tests backend
docker-compose exec backend pytest -v

# Lancer les tests avec coverage
docker-compose exec backend pytest --cov=app --cov-report=term-missing

# Accéder à PostgreSQL
docker-compose exec db psql -U bxchange -d bxchange_db

# Vider le cache Redis
docker-compose exec redis redis-cli FLUSHALL

# Installer deps frontend
cd frontend && npm install

# Dev frontend
cd frontend && npm run dev

# Build frontend
cd frontend && npm run build
```

---

## 🌍 Variables d'Environnement

```env
# Backend (.env)
DATABASE_URL=postgresql+asyncpg://bxchange:password@db:5432/bxchange_db
REDIS_URL=redis://redis:6379/0
SECRET_KEY=<générer avec: openssl rand -hex 32>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
ENCRYPTION_KEY=<générer avec: openssl rand -hex 32>
ENVIRONMENT=development
CORS_ORIGINS=["http://localhost:5173"]

# Frontend (.env)
VITE_API_URL=http://localhost:8000
```

---

## 🧪 Stratégie de Tests

- **Tests unitaires :** services/engines isolés avec mocks (zeep, httpx)
- **Tests d'intégration :** routes API avec base de test en mémoire (SQLite async)
- **Fixtures :** utilisateur test + tenant test dans `conftest.py`
- **Coverage cible :** > 80% sur `services/` et `api/`
- **CI :** pytest lancé automatiquement sur chaque push (GitHub Actions)

---

## 🐛 Pièges Connus

1. **zeep + WSDL malformés :** toujours wrapper l'appel dans try/except `zeep.exceptions.Fault`
2. **SQLAlchemy async :** ne jamais utiliser `session.execute()` en dehors d'un contexte async
3. **Chiffrement AES :** la clé doit être 32 bytes exactement — valider au démarrage
4. **JWT refresh :** invalider l'ancien refresh token après rotation (stocker en Redis)
5. **xmltodict :** les éléments uniques ne sont pas wrappés en liste — forcer avec `force_list`
6. **CORS :** en développement, autoriser `localhost:5173` ; en prod, domaine explicite uniquement
7. **Celery + async FastAPI :** ne pas appeler des coroutines depuis les tâches Celery sans `asyncio.run()`

---

## 📦 Modules Clés — Résumé Technique

### SOAPEngine (`services/soap_engine.py`)
- Charge le WSDL via `zeep.Client(wsdl_url)`
- Liste les opérations disponibles
- Exécute l'opération avec les paramètres fournis
- Retourne le XML brut de la réponse

### RESTEngine (`services/rest_engine.py`)
- Client `httpx.AsyncClient` avec timeout configurable
- Gère : Basic, Bearer, APIKey (header ou query), pas d'auth
- Retry automatique : 3 tentatives avec backoff exponentiel
- Retourne body + status + headers

### Transformer (`services/transformer.py`)
- `xmltodict.parse()` pour XML→dict
- Nettoyage des namespaces (`@xmlns`, `@xsi:...`)
- Aplatissement des structures imbriquées
- Détection et normalisation des arrays
- Application des règles de `transform_config` (renommage, sélection, filtrage)

### CryptoService (`services/crypto.py`)
- AES-256-GCM pour chiffrement des `auth_config`
- Clé depuis `settings.ENCRYPTION_KEY`
- `encrypt(data: dict) -> str` / `decrypt(token: str) -> dict`

---

*Ce fichier est la source de vérité du projet bxChange. Le mettre à jour à chaque changement d'architecture ou de décision technique.*
