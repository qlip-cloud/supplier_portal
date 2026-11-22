# Asignación de facturas sin OC (documenteme — crédito)

Branch: `feat/documenteme-assign-without-po`. Delivery: ask-on-risk. Tests: `python -m unittest` (archivo por archivo).

## Alcance

- Solo facturas a **crédito** (`nvfac_conv != "1"`). **Contado: sin cambios**, early return a la lógica actual.
- Núcleo **compartido** BC/GP (único punto de bifurcación sigue siendo la creación). Se habilita por configuración; encender primero en BC y validar GP en simulación.
- Reutiliza: fila catch-all de `qp_SP_AssignmentConfig` (`oc_type` y `headquarter` vacíos), `parse_purchase_orders`, `po_supplier_match`, banco de recepciones, selección manual de recibos y el patrón de `resources/documenteme/nc_reference.py` + `templates/modal/reference_nc.html`.
- Fuera de alcance: NC (ya tiene referencia), proveedor de servicio, delivery, contado, collection.

## Decisiones

- **D1**: Flag nuevo en `qp_SP_MasterSetup`: `assign_invoices_without_po` (Check, default `0`). No se usa `no_action` global.
- **D2**: Evaluación: flag ON + crédito + sin OC ⇒ **no se rechaza y se asigna**, antes de resolver la regla. Con OC, la cadena `proveedor > default` queda igual.
- **D3**: Semántica **A**: el flag asigna aunque el proveedor tenga `no_action`. Preparado para revertir con un único knob (`assign_when_no_action`, default `True`) en un predicado puro testeado en ambos sentidos.
- **D4**: El flag **no relaja la aprobación**: crédito sin OC sigue bloqueado por `_no_order_warning`; contado sigue con `cash_without_po_blocks`.
- **D5**: Estado nuevo `SO` ("Sin OC"): incluido en `ADVANCED_STATES`, fuera de `ANALYSIS_STATES`; no es candidato a aprobación ni rechazo, sí a asignación (reintento si no hubo destinatarios).
- **D6**: La OC manual se guarda en `qp_manual_purchase_order` (+ `qp_manual_po_assigned_by` / `qp_manual_po_assigned_at`) y se refleja en `nvfac_orde`. El re-sync preserva el valor manual **solo** cuando el origen viene vacío.
- **D7**: Multi-OC permitido (coma), validando cada OC por separado.
- **D8**: Roles para asignar OC: `Administrador Documenteme` / `Administrador Sede Documenteme` (mismos de NC y aprobación).
- **D9**: "Asignar y Aprobar" usa `approve_documents_core` (patrón NC); "Solo asignar" deja la factura en `E` y el pipeline normal la toma.
- **D10**: Sin email nuevo: la asignación se ve en la lista (`assigned_to_name` ya soporta múltiples) y cada movimiento deja constancia en el **timeline** (comentario visible al usuario). Si no hay destinatarios: `log_error`, comentario en el timeline y la factura queda en `E` (la alerta de 48h la expone).
- **D11**: Al asignar la OC manual, la factura **se reasigna al grupo del `oc_type` + `headquarter`**, igual que el flujo normal. Se resuelve primero el grupo nuevo: si resuelve destinatarios, se limpian `assigned_to` y `assigned_users` del catch-all y se corre el pipeline (que decide si la factura queda asignada o pasa a `V` porque el banco ya cubre el total). Si el grupo no resuelve destinatarios, **se conserva el catch-all** (nunca queda huérfana). Todo movimiento se registra en el timeline con el grupo anterior y el nuevo.
- **D12**: La fila catch-all no se comparte entre contado y crédito. Se agrega a `qp_SP_AssignmentConfig` el campo `invoice_type` (Select `Todos` / `Credito` / `Contado`, default `Todos`, visible en la lista). El matcher filtra por tipo de factura (`Todos` o vacío = aplica a ambas). La fila "sin OC" queda definida por `oc_type` y `headquarter` vacíos **+** `invoice_type` (`Credito` o `Contado`). `validate()` exige `Credito`/`Contado` cuando ambos campos están vacíos. Patch de backfill: las filas catch-all existentes pasan a `Contado` (su alcance efectivo actual).

## Specs

- **S1**: "necesitamos que las facturas que no tengan oc en vez de rechazarse, se asigne a usuarios que van a indicar las ordenes de compra a la q le pertenece y despues que se le asigne manualmente la orden de compra siga su flujo normal".
- **S2**: "marcar en el mastersetup que no se rechace las facturas q no tengan oc".
- **S3**: "en assignconfig se indiquen los usuarios q se le asignara las facturas sin oc, pero dejando el headquarter y el oc_type vacio, para indicar q todas las facturas con o sin headquarter y oc_type se le asigne si cumple con la condicion".
- **S4**: "usar la asignacion manual de la oc como lo hacemos en la nc q se tiene q seleccionar la referencia".
- **S5**: "una vez q se seleccione (una o mas) se dispara el flujo normal, q asigna, aprueba, rechaza la orden".
- **S6**: "esto q discutimos es solo para creditos, el contado debe funcionar como ya lo hace".
- **S7**: "vamos con la recomendacion A, pero debemos prepararlo de forma que si despues cambian de opinion y el no action no debe asignar podamos hacerlo sin mucho impacto".
- **S8**: "el cambio es requerido para bc, pero podemos evaluar el impacto en gp".
- **S9**: "el no action es sin accion total, y el default vacio si busca la configuracion en mastersetup".
- **S10**: Con el check marcado, el `no_action` del proveedor no impide la asignación del caso sin OC (semántica A).
- **S11** (supuesto): el flag aplica al crédito de ambos backends; se enciende primero en BC.
- **S12** (supuesto): estado nuevo `SO`; multi-OC permitido; roles de asignación iguales a NC.
- **S13**: "ese es el punto, tambien se lo asignara a los de contado, debemos poder diferenciarlos" → la config debe distinguir destinatarios de contado y de crédito sin OC.

## Diseño

### Predicado único (clave del cambio futuro)

`uses_cases/documenteme/no_purchase_order.py` (nuevo, puro, sin Frappe):

```python
DEFAULT_ASSIGN_WHEN_NO_ACTION = True

def has_effective_po(doc)            # parse_purchase_orders(doc["nvfac_orde"])
def is_without_po_credit(doc)        # crédito + no NC + no delivery + sin OC
def is_pending_purchase_order(doc, enabled, assign_when_no_action=True, supplier_rule=None)
def should_assign_without_po(doc, enabled, assign_when_no_action=True, supplier_rule=None,
                             in_queue=True, already_assigned=False)
def should_skip_reject_without_po(doc, enabled, assign_when_no_action=True, supplier_rule=None)
```

Revertir la semántica A = `assign_when_no_action=False` en un solo lugar, con test que cubre ambos sentidos.

### Puntos de integración

| Archivo | Cambio |
|---|---|
| `uses_cases/documenteme/auto_assign.py` | Rama crédito sin OC: destinatarios catch-all (`resolve_assignee_emails(None, None, has_receipt=False, invoice_type="Credito")`) + callback `mark_pending_oc_fn`; filtro `invoice_type` en `resolve_assignee_emails` |
| `uses_cases/documenteme/auto_reject.py` | `collect_rejectable` / `auto_reject` saltan docs con `should_skip_reject_without_po` |
| `resources/documenteme/auto_assign.py` | Resuelve el flag del `master_setup_source`, lo inyecta, implementa `mark_pending_oc` (estado `SO` + timeline) y `reassign_to_oc_group` (resolver grupo → limpiar catch-all → reasignar); `_load_assignment_rows` lee `invoice_type`; `get_assignee_emails` acepta `invoice_type` |
| `resources/collection_accounts/auto_assign.py` | Verificar que el lambda/callback propaga `invoice_type` (collection es crédito) |
| `doctype/qp_sp_assignmentconfig/qp_sp_assignmentconfig.json` + `.py` | Campo `invoice_type` (Select `Todos`/`Credito`/`Contado`, `in_list_view`), `validate()` exige tipo en la fila sin OC, `modified` |
| `patches/add_assignment_config_invoice_type.py` + `patches.txt` | Backfill: filas `oc_type`/`headquarter` vacíos → `Contado` |
| `resources/documenteme/auto_reject.py` | Inyecta el flag y el predicado de skip |
| `services/document_sync.py` | `ADVANCED_STATES += ("SO",)`; preservar OC manual; `SO → E` si el origen trae OC |
| `infrastructure/adapters/master_setup_source.py` + `simulation/master_setup_source.py` | `assign_without_po_enabled()` |
| `resources/documenteme/purchase_order_reference.py` (nuevo) | `get_purchase_order_candidates`, `assign_purchase_order` |
| `www/monitor/documenteme/index.js` / `index.html` | Modal OC, opción `SO` en el select de estado |
| `templates/list/documenteme_sales_invoices/list.html` | Icono "Asignar OC" (columna OC), badge "Sin OC" |
| `templates/modal/reference_po.html` (nuevo) | Modal multi-selección calcado de `reference_nc.html` |
| `uses_cases/documenteme/timeline.py` | Label `SO` |
| `simulation/assign_memory.py` / `reject_memory.py` / `documents_memory.py` / `seeds.py` | Paridad de simulación |
| `doctype/qp_sp_documentdetail/qp_sp_documentdetail.json` | 3 campos nuevos + `modified` |
| `doctype/qp_sp_mastersetup/qp_sp_mastersetup.json` | 1 Check + `modified` |

### Orden de evaluación (crédito sin OC)

1. `assign_invoices_without_po` ON + crédito + sin OC ⇒ marcar `SO`, asignar la fila catch-all `invoice_type="Credito"`, nunca rechazar.
2. Si hay OC: pipeline actual sin cambios (assign por banco, approve por validación, reject por regla).
3. Contado: early return, pipeline actual (no se toca).

### Cómo se identifican los destinatarios (config)

- **Fila sin OC de crédito**: `qp_SP_AssignmentConfig` con `oc_type` vacío, `headquarter` vacío e `invoice_type = "Credito"`. Es la única que matchea el crédito sin OC.
- **Fila sin OC de contado**: mismos campos vacíos + `invoice_type = "Contado"` (comportamiento actual del contado, sin cambios).
- Puede haber más de una fila por tipo: se suman.
- **Hijos**: `users` (`qp_SP_AssignmentConfigUser.user_email` + `receipt_preference`) y `roles` (`qp_SP_AssignmentConfigRole.role`, que se expande a usuarios habilitados con ese rol).
- **Resolución**: `get_assignee_emails(None, None, has_receipt=False, invoice_type="Credito")` → `resolve_assignee_emails(None, None, ..., invoice_type="Credito")` → filas catch-all del tipo + wildcards `"No aplica"`.
- **Filtro por tipo**: `row.invoice_type in (None, "", "Todos", invoice_type)`. Vacío/desconocido = `Todos` (compatibilidad).
- **Filtros de usuario**: con `has_receipt=False` se excluyen los usuarios con `receipt_preference="Con Recepcion"` (solo pasan `Ambos` y `Sin Recepcion`); `resolve_assignee_users` descarta emails inexistentes o deshabilitados.
- **Sin destinatarios**: la unión vacía no asigna; log + comentario en el timeline y la alerta de 48h expone la factura.
- `oc_type="No aplica"` es **wildcard** (matchea con y sin OC). Para "solo sin OC" la fila correcta es `oc_type`/`headquarter` vacíos + `invoice_type`.
- **Collection** comparte la config y el matcher: sus facturas son crédito (`nvfac_conv="2"`), así que matchean `Todos`/`Credito` y nunca `Contado`.
- **UX**: `invoice_type` va `in_list_view`, así la fila se identifica como "Credito" o "Contado" aunque `oc_type`/`headquarter` estén vacíos.

## Tasks

- [x] **T1** (S1, S2, S6, S7, S10) Predicado puro + tests. Route: inline. Files: `uses_cases/documenteme/no_purchase_order.py`, `tests/test_no_purchase_order.py`. Acepta: flag OFF = comportamiento actual; ON = crédito sin OC pendiente; contado y NC nunca; `no_action` no bloquea con knob `True`; knob `False` sí bloquea (test del cambio futuro).
- [x] **T2** (S2, S9, S10) Flag en MasterSetup + adaptadores real/memoria + tests. Route: inline. Files: `qp_sp_mastersetup.json`, `master_setup_source.py` (real y sim), `tests/test_master_setup_source*.py`. Acepta: default `0`; lectura real y de store; `bench migrate` requerido.
- [x] **T2b** (S3, D12) Diferenciación contado/crédito en la config. Route: inline. Files: `qp_sp_assignmentconfig.json`, `qp_sp_assignmentconfig.py`, `patches/add_assignment_config_invoice_type.py`, `patches.txt`, `tests/test_assignment_config_invoice_type.py`. Acepta: campo `invoice_type` con default `Todos` y `in_list_view`; `validate()` exige `Credito`/`Contado` cuando `oc_type` y `headquarter` están vacíos; backfill de filas existentes a `Contado`; una fila `Credito` no matchea contado y viceversa.
- [x] **T3** (S1, S3, S6, S7, D12) Asignación de crédito sin OC + estado `SO`. Route: inline. Files: `uses_cases/documenteme/auto_assign.py`, `resources/documenteme/auto_assign.py`, `tests/test_auto_assign.py`, `tests/test_auto_assign_infra.py`. Acepta: `invoice_type` se propaga por el callback (crédito=`Credito`, contado=`Contado`); catch-all del tipo resuelve destinatarios (no se cruzan con contado); `assigned_users` idempotente; estado `SO` + timeline; sin destinatarios = log y sin asignación; contado intacto; tests con lambdas actualizados a la nueva firma.
- [x] **T4** (S1, S9, S10) Guard de rechazo. Route: inline. Files: `uses_cases/documenteme/auto_reject.py`, `resources/documenteme/auto_reject.py`, `tests/test_auto_reject.py`, `tests/test_auto_reject_infra.py`. Acepta: con flag ON un crédito sin OC nunca entra a `PR`; con flag OFF se rechaza igual que hoy; contado intacto.
- [x] **T5** (S2, S5, D6) Persistencia y re-sync. Route: inline. Files: `services/document_sync.py`, `doctype/qp_sp_documentdetail.json`, tests de sync/memoria. Acepta: `nvfac_orde = origen or manual`; `SO` sobrevive al re-sync; `SO → E` cuando el origen trae OC; sin migrate no hay campo (documentar).
- [x] **T6** (S4, S5, D7, D8, D11, D12) Endpoint manual de OC + reasignación al grupo de la OC. Route: inline. Files: `resources/documenteme/purchase_order_reference.py`, `resources/documenteme/auto_assign.py` (`reassign_to_oc_group`), `tests/test_manual_purchase_order.py`. Acepta: candidatas del proveedor; valida existencia, `po_supplier_match` y `qp_order_confirmation_no == número`; multi-OC; escribe campos + estado `E`; **resuelve el grupo `oc_type`/`headquarter` con `invoice_type="Credito"`, limpia el catch-all y reasigna** (union de OCs en multi-OC); si el grupo no resuelve destinatarios conserva los actuales; si el banco cubre el total no deja asignados (flujo normal `V`→aprobación); timeline con grupo anterior, grupo nuevo y actor; "Solo asignar" y "Asignar y Aprobar" (vía `approve_documents_core`); permisos.
- [x] **T7** (S4, S5) Front. Route: inline. Files: `templates/modal/reference_po.html`, `templates/list/documenteme_sales_invoices/list.html`, `www/monitor/documenteme/index.js`, `www/monitor/documenteme/index.html`, `www/monitor/documenteme/index.py`. Acepta: icono visible solo en crédito sin OC no final; modal multi-selección con búsqueda; opción `SO` en el filtro; badge "Sin OC"; recarga/refresh tras asignar.
- [x] **T8** (S1, S5, S10, D11, D12) Paridad de simulación. Route: inline. Files: `simulation/assign_memory.py`, `simulation/reject_memory.py`, `simulation/documents_memory.py`, `simulation/collection_invoices_memory.py`, `simulation/seeds.py`, `tests/test_sim_assign_in_memory.py`, `tests/test_sim_reject_in_memory.py`, `tests/test_documents_memory.py`. Acepta: mismos escenarios que real (incluye `invoice_type` en la carga de filas y en los lambdas, reasignación al grupo de la OC y constancia en el timeline); flag sembrado en seeds; collection memory propaga el tipo.
- [x] **T9** (S8) Escenarios GP. Route: inline. Files: tests de simulación GP + `docs/FLUJO-GP-DOCUMENTEME.md`. Acepta: crédito sin OC asignado no rompe tipo 1/2; con OC con recepciones = tipo 1; con OC sin recepciones = tipo 2 y homologación; servicio/NC intactos.
- [ ] **T10** (all) Verificación y contexto. Route: inline. Acepta: suite por archivo verde; docs (`docs/ASIGNACION-AUTOMATICA-DOCUMENTEME.md`, skill `documenteme`, `AGENTS.md`) actualizados **con confirmación del usuario**.

## Slices de entrega (ask-on-risk)

- Slice 1: T1–T5 + T2b (núcleo y configuración, sin UI), ~350 líneas.
- Slice 2: T6 (endpoint sin UI), ~150 líneas.
- Slice 3: T7 (front), ~200 líneas.
- Slice 4: T8–T10 (simulación, GP, docs).
- Al superar ~400 líneas autoradas se pregunta una vez por la estrategia de cadena (`stacked-to-main` o `feature-branch-chain`) y se registran aquí los límites de cada PR.

## Verification

Ejecutado el 2026-11-17 con el python del bench (`/workspace/development/mentum_localhost/env/bin/python -m unittest`), archivo por archivo:

- `test_no_purchase_order` (30), `test_assignment_config_invoice_type` (6), `test_manual_purchase_order` (19), `test_auto_assign` (49), `test_auto_reject` (63), `test_auto_assign_receipt_preference`, `test_auto_assign_infra` (43), `test_auto_reject_infra`, `test_approve` (136), `test_auto_approve` (31), `test_documents_memory` (28), `test_document_sync` (16), `test_sim_assign_in_memory` (16), `test_sim_reject_in_memory`, `test_sim_scenario_in_memory`, `test_sim_approve_in_memory`, `test_sim_view_in_memory`, `test_collection_sim_in_memory`, `test_collection_scenario_in_memory`, `test_auto_approve_confirmation`, `test_approve_confirmation`, `test_documenteme_runtime`, `test_timeline_memory`, `test_sim_master_setup_source`: **OK**.
- GP / aprobación: `test_gp_invoice_builder`, `test_sim_gp_approve_in_memory`, `test_sim_gp_documenteme_in_memory`, `test_sim_gp_service_supplier_in_memory`, `test_collection_gp_approve`, `test_no_receipt_invoice`, `test_bc_credit_note`, `test_approve_base_infra`, `test_approve_base_simulation`, `test_approve_selected_receipts`: **OK**.
- Fallo pre-existente verificado contra `git archive HEAD` en `/tmp`: `tests/test_data_facade.py::test_get_v_doc_names_real_devuelve_strings` (`RuntimeError: no object bound to session`). No lo causa este cambio.

Comandos de referencia:

- `python -m unittest qp_supplier_front.tests.test_no_purchase_order`
- `python -m unittest qp_supplier_front.tests.test_assignment_config_invoice_type`
- `python -m unittest qp_supplier_front.tests.test_auto_assign`
- `python -m unittest qp_supplier_front.tests.test_auto_assign_infra`
- `python -m unittest qp_supplier_front.tests.test_auto_reject`
- `python -m unittest qp_supplier_front.tests.test_auto_reject_infra`
- `python -m unittest qp_supplier_front.tests.test_manual_purchase_order`
- `python -m unittest qp_supplier_front.tests.test_approve` (sin regresiones; crédito sin OC sigue bloqueado)
- `python -m unittest qp_supplier_front.tests.test_documents_memory` y `test_sim_assign_in_memory` / `test_sim_reject_in_memory` / `test_sim_approve_in_memory`
- `python -m unittest qp_supplier_front.tests.test_sim_gp_approve_in_memory` / `test_sim_gp_documenteme_in_memory`
- Smoke manual: `bench --site <sitio> migrate` + refresh del front + asignar OC + verificar estado y payload.

## Riesgos / limitaciones conocidas

- El re-sync pisa `nvfac_orde` (`_set_document_detail_fields`); mitigado con campo manual y regla `origen or manual`, cubierto por test.
- Crédito exige OC + banco de recepciones que cubra el total; puede requerir la selección manual de recibos ya existente.
- Con OC aparece el gate de superaprobación (`PSA`).
- Sin destinatarios en el catch-all no hay asignación inicial: log + timeline + alerta de 48h; no se inventa fallback.
- Al reasignar por OC, si el grupo de la OC no resuelve destinatarios se **conserva** el catch-all (decisión deliberada para no dejar la factura huérfana).
- Si el banco de recepciones de la OC ya cubre el total, la factura no queda asignada: pasa a `V` y sigue el flujo normal de aprobación.
- Una factura que ya entró a `PR` no se rescata (`get_candidates` la excluye).
- GP: con OC sin recepciones el envío cae en tipo 2 y exige homologación de todas las líneas.
- Migración: el patch backfillea las filas catch-all existentes a `Contado`. Si el negocio quiere que una fila existente también cubra crédito, debe editarla a `Todos` o crear la fila `Credito`.
- Cambiar la firma de `resolve_emails_fn` obliga a actualizar lambdas de tests y de `simulation/collection_invoices_memory.py`.

## Log

- **L1**: "vamos a hacer un cambio en el proceso de asignaciones / el cambio es requerido para bc, pero podemos evaluar el impacto en gp / necesitamos que las facturas que no tengan oc en vez de rechazarse, se asigne a usuarios que van a indicar las ordenes de compra a la q le pertenece y despues que se le asigne manualmente la orden de compra siga su flujo normal" + los 4 puntos de la propuesta original.
- **L2**: Análisis read-only: crédito sin OC no se asigna y el rechazo no mira asignación; el re-sync pisa `nvfac_orde`; ya existen catch-all y el flujo NC de referencia; impacto GP (tipo 1/2, homologación).
- **L3**: "esto q discutimos es solo para creditos, el contado debe funcionar como ya lo hace".
- **L4**: "vamos con la recomendacion A, pero debemos prepararlo de forma que si despues cambian de opinion y el no action no debe asignar podamos hacerlo sin mucho impacto".
- **L5**: "ahora crea el plan detallando lo q haremos".
- **L6**: "La factura conserva los asignados del catch-all: lo ideal es q una vez asignada la oc, se re-asigna al grupo del oc_type y headquarter como funciona normalmente, lo q si podemos es dejar contancia en el log q se le muestra al usuario" → decisión **D11** y ajuste de T6/T8/riesgos.
- **L7**: "ese es el punto, tambien se lo asignara a los de contado, debemos poder diferenciarlos" → decisión **D12** (`invoice_type` en `qp_SP_AssignmentConfig`), tarea T2b y ajuste de T3/T6/T8/riesgos.
- **L8**: Implementado en la rama `develop-no-reject-oc` (desde `develop-documenteme`): `a8b8500` config + predicado, `b0ece81` flujo núcleo + simulación, `33c6b5f` endpoint manual de OC, `5e30c48` front. T1-T9 verificadas; T10 (docs/skill/AGENTS) pendiente de confirmación del usuario.
