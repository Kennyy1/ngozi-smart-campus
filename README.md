# Ngozi Smart Campus

Ngozi Smart Campus is an intelligent, secure and scalable smart campus platform developed as part of a PhD research project.

The platform will provide unified access to institutional services through:

- A web application
- An Android mobile application
- A FastAPI backend
- A middleware integration layer
- A PostgreSQL database
- Role-based student, lecturer and administrator portals
- An AI-powered campus assistant
- Institutional service simulations
- Analytics, logging and system monitoring

## Local development

The API requires PostgreSQL and reads its configuration from `backend/.env` (copy
`backend/.env.example`). Start it with:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

The API and interactive documentation are available at
`http://127.0.0.1:8000` and `http://127.0.0.1:8000/docs`.

The web application is a React, TypeScript, and Vite application. Its API URL is
configured once through `VITE_API_BASE_URL`:

```bash
cd web
cp .env.example .env
npm install
npm run dev
```

Open `http://localhost:5173`. Run frontend checks with `npm test` and
`npm run build`. The default backend CORS origins allow the localhost and
127.0.0.1 Vite development origins; deployments should set `CORS_ORIGINS` to a
comma-separated list of their exact frontend origins.

## Project status

The foundation includes the FastAPI backend and role-protected web portals for
students, lecturers, and administrators.
