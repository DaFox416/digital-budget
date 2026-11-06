# Digital Budget

Webapp de finanzas personales para México: cuentas de débito, efectivo y crédito, ciclos de corte y pago, compras a MSI y un **modo ahorro** que separa el saldo real del dinero disponible.

## Fuente de verdad

@docs/PLANEACION.md

Lee la planeación antes de proponer o implementar algo. Respeta el "Registro de decisiones". Cuando el usuario tome una decisión nueva, agrégala al registro con su fecha y actualiza la sección afectada. Marca las casillas del plan conforme se completen.

## Cómo trabajar conmigo

- Conversa en español. Código, nombres de variables, commits y comentarios en inglés.
- Trabajo solo y quiero aprender full stack: explica brevemente el porqué de las decisiones técnicas nuevas.
- Antes de implementar algo no trivial, propón un plan corto y espera mi aprobación.
- Commits pequeños con Conventional Commits (`feat:`, `fix:`, `test:`, `chore:`, `docs:`).

## Reglas que no se rompen

- Dinero: `NUMERIC(12,2)` en Postgres y `Decimal` en Python. Nunca `float`. En el frontend, montos como string o centavos enteros.
- Las reglas de negocio viven en `backend/app/domain/` como Python puro, sin FastAPI ni SQLAlchemy, y siempre con pruebas.
- Invariante del modo ahorro, probado en cada operación:
  `saldo real = disponible + apartado + deuda de tarjetas + ahorros con meta + sobrante`
- Todo movimiento guarda monto real y monto contable (iguales en modo simple).
- Borrado lógico de movimientos; nunca borrado físico.
- `user_id` en todas las tablas desde el inicio.
- Sin dependencias externas de pago; todo corre en local con Docker.

## Stack

FastAPI + Pydantic v2 + SQLAlchemy 2.0 + Alembic + PostgreSQL 16 · React 19 + TypeScript + Vite + TanStack Query + Tailwind v4 · pytest, Vitest, Playwright · Docker Compose · GitHub Actions.

## Comandos

Se completarán conforme se cree la estructura (levantar con Docker, migraciones, pruebas, lint).

**Docker (forma principal de levantar la app)**, desde la raíz:

- Levantar todo: `docker compose up` (o `-d` para segundo plano; `--build` si cambian dependencias)
- Frontend `http://localhost:5173` · API docs `http://localhost:8000/docs` · Postgres `localhost:5432` (usuario, contraseña y BD: `budget`)
- Logs: `docker compose logs -f backend` · Detener: `docker compose down` (`-v` borra también los datos de Postgres)
- Comandos dentro de un contenedor: `docker compose exec backend pytest`, `docker compose exec db psql -U budget`
- La recarga automática usa polling (Windows no propaga eventos de archivos a los contenedores).

**Backend** (desde `backend/`, con el venv `.venv` de Python 3.12):

- Instalar: `py -3.12 -m venv .venv` y `.venv\Scripts\python -m pip install -e ".[dev]"`
- Servidor local: `.venv\Scripts\python -m uvicorn app.main:app --reload` (docs en `http://localhost:8000/docs`)
- Pruebas: `.venv\Scripts\python -m pytest`
- Lint y formato: `.venv\Scripts\python -m ruff check .` y `.venv\Scripts\python -m ruff format .`
- Tipos: `.venv\Scripts\python -m mypy app tests`
- El cliente de pruebas usa `httpx2` (Starlette 1.10 marca `httpx` como obsoleto).
- Todas las rutas viven bajo `/api/v1` (por ejemplo `/api/v1/health`).

**Frontend** (desde `frontend/`, Node 26):

- Instalar: `npm install`
- Servidor local: `npm run dev` (en `http://localhost:5173`; reenvía `/api` al backend en `:8000`, configurable con `API_PROXY_TARGET`)
- Pruebas: `npm test` (una vez) o `npm run test:watch`
- Build: `npm run build`
