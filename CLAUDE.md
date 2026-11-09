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
  `saldo real = disponible + apartado + deuda de tarjetas + ahorros con meta + sobrante − MSI por cargar`
- Todo movimiento guarda monto real y monto contable (iguales en modo simple); excepción: el gasto de una compra a MSI tiene contable 0 y el contable vive en sus mensualidades.
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

**Respaldo de la BD** (antes de cualquier `docker compose down -v`; los archivos van a `backups/`, que está en `.gitignore` porque tienen datos reales):

- Respaldar:
  `docker compose exec db pg_dump -U budget -d budget --format=custom -f /tmp/budget.dump`
  `docker compose cp db:/tmp/budget.dump backups/budget-AAAA-MM-DD.dump`
- Restaurar (reemplaza los datos actuales):
  `docker compose stop backend`
  `docker compose cp backups/budget-AAAA-MM-DD.dump db:/tmp/budget.dump`
  `docker compose exec db pg_restore -U budget -d budget --clean --if-exists /tmp/budget.dump`
  `docker compose start backend` (aplica las migraciones que falten si el respaldo es viejo)
- El archivo se genera dentro del contenedor y se copia con `docker compose cp`: el formato `custom` es binario y la redirección `>` de PowerShell lo puede corromper.
- En Git Bash, anteponer `MSYS_NO_PATHCONV=1` (o `export` una vez): MSYS convierte `/tmp/...` en una ruta de Windows. En PowerShell no hace falta.
- Solo se respalda `budget`; `budget_test` se recrea sola.

**Backend** (desde `backend/`, con el venv `.venv` de Python 3.12):

- Instalar: `py -3.12 -m venv .venv` y `.venv\Scripts\python -m pip install -e ".[dev]"`
- Servidor local: `.venv\Scripts\python -m uvicorn app.main:app --reload` (docs en `http://localhost:8000/docs`)
- Pruebas: `.venv\Scripts\python -m pytest`
- Lint y formato: `.venv\Scripts\python -m ruff check .` y `.venv\Scripts\python -m ruff format .`
- Tipos: `.venv\Scripts\python -m mypy app tests`
- El cliente de pruebas usa `httpx2` (Starlette 1.10 marca `httpx` como obsoleto).
- Todas las rutas viven bajo `/api/v1` (por ejemplo `/api/v1/health`).
- Migraciones: `.venv\Scripts\alembic upgrade head`; nueva migración tras cambiar modelos: `.venv\Scripts\alembic revision --autogenerate -m "describe change"` (revisar siempre el archivo generado); verificar que modelos y migraciones coinciden: `.venv\Scripts\alembic check`. En Docker, el backend aplica las migraciones al arrancar.
- Las pruebas de API necesitan el Postgres de Docker; usan la BD `budget_test` (se crea y migra sola, y cada prueba se revierte).
- Capas: `api/` (HTTP) → `services/` (casos de uso, `commit`) → `domain/` (reglas puras) y `repositories/` (consultas, siempre filtradas por `user_id`).
- Si `backend/app` importa una librería nueva, agrégala también a `additional_dependencies` del hook de mypy en `.pre-commit-config.yaml`.

**Frontend** (desde `frontend/`, Node 26):

- Instalar: `npm install`
- Servidor local: `npm run dev` (en `http://localhost:5173`; reenvía `/api` al backend en `:8000`, configurable con `API_PROXY_TARGET`)
- Pruebas: `npm test` (una vez) o `npm run test:watch`
- Lint: `npm run lint` · Formato: `npm run format` (o `format:check`) · Tipos: `npm run typecheck`
- Build: `npm run build`
- Tipos de la API: `npm run api:types` (con el backend levantado; otra URL con `OPENAPI_URL`). Regenera `src/api/schema.d.ts`, que se sube al repo y no se edita a mano. Correrlo cada vez que cambie un esquema o una ruta del backend.
- `openapi-typescript` pide TypeScript 5 como peer; un `overrides` en `package.json` le da nuestro TS 6. Quitarlo cuando publique una versión compatible.
- TypeScript 6.0, no 7: typescript-eslint aún no soporta TS 7.

**pre-commit** (desde la raíz; se instala con las dependencias de desarrollo del backend):

- Activar el hook de Git (una vez por clon): `backend\.venv\Scripts\pre-commit install`
- Correr todo a mano: `backend\.venv\Scripts\pre-commit run --all-files`
- Revisa formato y lint del backend (Ruff, mypy) y del frontend (Prettier, ESLint, tsc). Las versiones de Ruff y mypy en `.pre-commit-config.yaml` deben coincidir con las de `backend/pyproject.toml`.
- Si cambias dependencias del frontend, recrea su contenedor: `docker compose up -d --build -V frontend` (`-V` renueva el volumen de `node_modules`).
