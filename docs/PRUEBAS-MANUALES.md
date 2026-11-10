# Pruebas manuales con datos reales

Guion para comparar la app con un estado de cuenta real antes del demo. La meta es encontrar diferencias en las reglas de tarjetas y MSI, y fricciones de captura para el formulario del día 11.

> **Tus números no van al repo.** Anota resultados en `docs/pruebas-manuales.local.md` (está en `.gitignore`). Para revisarlos con Claude, comparte solo las diferencias, sin datos de tu cuenta.

Mientras no exista el formulario de captura, todo se captura desde Swagger: `http://localhost:8000/docs` → endpoint → **Try it out** → **Execute**. Los montos se escriben positivos y como texto (`"387.56"`); el tipo decide el signo. Las fechas van como `"AAAA-MM-DD"`.

## 1. Preparación

1. Si la base tiene datos que quieras conservar, respáldalos (ver "Respaldo de la BD" en `CLAUDE.md`).
2. Borra los datos de desarrollo (la tarjeta "Smoke TDC"). **Esto borra toda la base:**
   `docker compose down -v`
3. Levanta todo: `docker compose up -d` y abre `http://localhost:5173`. Debe decir "API: Conectada" y "Aún no tienes cuentas".
4. Respalda la base vacía como punto de partida: `backups/budget-AAAA-MM-DD-vacia.dump`.

## 2. Elegir el ciclo a comparar

Toma un estado de cuenta **ya cerrado** de una tarjeta real. Idealmente uno en el que el ciclo anterior se pagó completo: la regla 8 aún no arrastra saldo no pagado (límite conocido).

Ten a la mano: fecha de corte, fecha límite de pago, saldo anterior, cargos y abonos del periodo, mensualidades MSI (número y monto de cada una), pagos y "pago para no generar intereses".

## 3. Dar de alta las cuentas

`POST /api/v1/accounts`

Débito (saldo de hoy en el banco):

```json
{ "type": "debit", "name": "BBVA", "initial_balance": "5000.00" }
```

Tarjeta (el saldo inicial es el **saldo anterior** del estado de cuenta, en negativo):

```json
{
  "type": "credit",
  "name": "TDC Oro",
  "initial_balance": "-634.00",
  "credit": {
    "credit_limit": "20000",
    "cutoff_day": 15,
    "payment_due_rule": "fixed_day",
    "payment_due_value": 5
  }
}
```

- `payment_due_rule`: `fixed_day` (siempre el día N del mes) o `days_after_cutoff` (N días después del corte), según tu banco.
- Si te equivocas, corrige con `PATCH /api/v1/accounts/{id}`; por ejemplo `{ "credit": { "cutoff_day": 20 } }`.

Guarda los `id` de las respuestas: los necesitas para capturar.

## 4. Capturar el ciclo

**Cargos y devoluciones del periodo** · `POST /api/v1/movements`

```json
{ "account_id": "<id de la tarjeta>", "type": "expense", "amount": "387.56", "occurred_on": "2026-11-05", "description": "Cine" }
```

Una devolución es `"type": "income"` en la tarjeta. Las categorías salen de `GET /api/v1/categories` (campo `category_id`, opcional).

**Compras a MSI vigentes** · `POST /api/v1/installment-plans`, con la fecha **original** de compra:

```json
{ "account_id": "<id de la tarjeta>", "total": "12000", "months": 12, "purchased_on": "2026-08-10", "description": "Laptop" }
```

**Pagos a la tarjeta** · `POST /api/v1/transfers`, incluidos los hechos después del corte:

```json
{ "source_account_id": "<id de débito>", "destination_account_id": "<id de la tarjeta>", "amount": "634", "occurred_on": "2026-11-18" }
```

## 5. Comparar

`GET /api/v1/cards/{id}/statement?cycle=<fecha de corte>` y la pantalla de inicio. Llena la tabla en tu archivo `.local.md`:

| Concepto | Banco | App | ¿Coincide? | Nota |
| --- | --- | --- | --- | --- |
| Fecha de corte (`cutoff`) | | | | |
| Fecha límite (`payment_due`) | | | | |
| Cargos del periodo (`regular_charges`) | | | | |
| Mensualidades MSI: número y monto de cada una (`installments`) | | | | |
| Pagos después del corte (`payments_after_cutoff`) | | | | |
| Pago para no generar intereses (`payment_for_no_interest`) | | | | |
| Deuda total (pantalla: "Debes") | | | | |
| Crédito disponible | | | | |
| Saldo real (pantalla) contra tus cuentas de débito | | | | |

Si algo no coincide, anota qué movimiento lo explica: una compra en el día de corte, una mensualidad que el banco pone en otro ciclo, un pago que cae en otra fecha, etc.

## 6. Editar, borrar y deshacer

Después de cada paso, recarga la pantalla y revisa que los saldos y el resumen cambien como esperas.

| Prueba | Cómo | Qué debe pasar |
| --- | --- | --- |
| Corregir un monto | `PATCH /api/v1/movements/{id}` con `{ "amount": "400" }` | Cambian el saldo y los cargos del ciclo |
| Cambiar un gasto de ciclo | `PATCH` con `occurred_on` = día siguiente al corte | Sale de ese estado de cuenta y entra al siguiente |
| Borrar y deshacer una transferencia | `DELETE /api/v1/movements/{id}` y luego `POST /api/v1/movements/{id}/restore` | Desaparecen y vuelven las dos partes |
| Borrar y deshacer una compra a MSI | `DELETE` del `movement_id` del plan y luego `restore` | Sus mensualidades salen y vuelven al estado de cuenta; el crédito se libera y se vuelve a ocupar |
| Corregir el día de corte | `PATCH /api/v1/accounts/{id}` con `{ "credit": { "cutoff_day": N } }` | Las mensualidades se mueven a los nuevos cortes (vuelve a dejarlo como estaba al terminar) |

## 7. Fricciones de captura

Anota lo que fue tedioso, lento o confuso. Sirve para diseñar el formulario del día 11:

- ¿Qué campos capturaste en casi todos los movimientos? ¿Cuáles nunca?
- ¿Qué valores por defecto te habrían ahorrado tiempo (cuenta, fecha, categoría)?
- ¿Algún nombre o mensaje de error que no se entendió?
- ¿Algo que la pantalla de inicio debería mostrar y no muestra?

## 8. Cerrar

1. Respalda la base con tus datos: `backups/budget-AAAA-MM-DD.dump`.
2. Comparte con Claude las diferencias y fricciones (sin datos de tu cuenta) para decidir qué se corrige antes del demo.

## 9. Segunda ronda (mié 11 nov): sistema completo y modo ahorro

Se hace sobre la base que ya tiene tus datos reales. **No uses `docker compose down -v`.**

1. Respalda primero: `backups/budget-2026-11-11-antes.dump`.
2. Repite rápido la sección 5 con lo capturado desde el día 9 (estado de cuenta, deuda y saldo real) para confirmar que nada cambió con las migraciones del día 10.
3. Sigue los pasos de esta tabla. Después de cada paso, revisa `GET /api/v1/summary`: las siete cifras deben cuadrar con
   `real_balance = available + set_aside + card_debt + savings_goals + leftover − installments_pending`.

| Paso | Cómo | Qué debe pasar |
| --- | --- | --- |
| Activar el modo ahorro | `PATCH /api/v1/preferences` con `{ "mode": "savings" }` | Responde `rounding_multiple: 10`; las cifras no cambian (el modo solo cambia lo que muestra el frontend) |
| Apartar un gasto | `POST /api/v1/commitments` con `{ "name": "Luz", "amount": "500" }` | `set_aside` sube 500 y `available` baja 500 |
| Gasto con contable redondeado | `POST /api/v1/movements` con `"amount": "387.56"` y `"accounting_amount": "400"` | `available` baja 400 y `leftover` sube 12.44 |
| Compra con tarjeta redondeada | Igual, en la tarjeta (`"634"` y `"640"`) | Sube `card_debt` 634, baja `available` 640, `leftover` +6 |
| Pagar el apartado | Gasto de `"487"` con `"commitment_id"` de la luz, sin contable | Contable −500; `set_aside` baja 500, `available` no cambia, `leftover` +13 |
| Mover el pago a otro apartado | Crea "Agua" de 300 y `PATCH /api/v1/movements/{id}` con `{ "commitment_id": "<id agua>" }` | Contable −487 (el mayor entre 487 y 300); Luz vuelve a pendiente y Agua queda pagada |
| Quitar el apartado del pago | `PATCH` con `{ "commitment_id": null }` | Contable = real (−487); los dos apartados quedan pendientes |
| Borrar y deshacer un apartado | `DELETE /api/v1/commitments/{id}` y luego `POST /api/v1/commitments/{id}/restore` | Sale y vuelve a `set_aside`. Si está pagado responde 409: borra antes el pago |
| Liberar sobrante | `GET /summary` → `leftover_releasable`; `POST /api/v1/leftover-releases` con ese monto | `available` sube y `leftover` baja por igual. Un monto que no sea múltiplo de 10 responde 422 |
| Deshacer la liberación | `DELETE /api/v1/leftover-releases/{id}` | Las cifras vuelven a como estaban |
| MSI en modo ahorro | Si tienes una compra a MSI vigente, revisa `installments_pending` | Igual a las mensualidades con fecha de cargo posterior a hoy |

4. Compara `available` contra lo que tú calculas a mano (tu Excel). Si no coincide, anota el paso donde se separó y la diferencia, sin datos de tu cuenta.
5. Borra o deshaz los apartados y liberaciones de prueba que no quieras conservar, y respalda: `backups/budget-2026-11-11.dump`.
