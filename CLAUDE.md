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

FastAPI + Pydantic v2 + SQLAlchemy 2.0 + Alembic + PostgreSQL 16 · React 18 + TypeScript + Vite + TanStack Query + Tailwind · pytest, Vitest, Playwright · Docker Compose · GitHub Actions.

## Comandos

Se completarán conforme se cree la estructura (levantar con Docker, migraciones, pruebas, lint).
