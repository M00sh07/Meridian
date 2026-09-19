# Meredian

Repository Intelligence for understanding, exploring, and safely changing software.

## Current Development Phase
**Phase 0 - Foundation**: A working monorepo setup with a Next.js frontend and a FastAPI backend with a health endpoint.

## Project Structure
* `apps/web`: Next.js + TypeScript frontend
* `apps/api`: Python + FastAPI backend
* `services/ingestion`: Repository ingestion service (future)
* `services/parser`: AST parser (future)
* `services/analytics`: Code metrics (future)
* `services/ml`: ML Risk model (future)
* `packages/types`: Shared types
* `packages/config`: Shared configuration
* `docs/architecture`: Architecture documentation
* `docs/decisions`: Architectural decision records

## Local Setup

### Backend (apps/api)
```bash
cd apps/api
python -m venv .venv
# On Windows
.venv\Scripts\activate
# On Unix
# source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend (apps/web)
```bash
cd apps/web
npm install
npm run dev
```

The frontend runs at http://localhost:3000 and the backend API runs at http://localhost:8000.
