# Simulación del flujo documenteme

Guía de referencia del **modo simulador** de documenteme (`qp_supplier_front`).
Este documento es el punto de entrada para agentes y QA: describe qué se
simula, cómo habilitarlo, el escenario completo de 11 facturas y cómo correr
los tests. Vivimos en código con "data real" intacta (modo real no cambia).

---

## 1. Qué es

Con el flag **`qp_SP_MasterSetup.documenteme_simulation`** activo, el flujo
documenteme se ejecuta de extremo a extremo **en memoria** (MemoryStore de
sesión) **sin documenteme, Business Central ni middleware**, y **sin escribir
en la DB real** ni una sola fila de las facturas simuladas:

- Sync entrante (fases 1-2) servido por **fixtures JSON**.
- Auto-assign, auto-aprove, auto-rechazo y confirmación BC simulados.
- Creación en BC (doc_number `SIM*`) y eventos 030/032/031/033 simulados.
- La vista `/documenteme/sales_invoices` lee el store de la sesión.

El único gate es el flag (`is_simulation_enabled()` en
`resources/documenteme/runtime.py`). El flag solo lo alterna `Administrator`
(controller del doctype `qp_sp_mastersetup.py`). Si el flag **no puede
leerse** (columna ausente / OperationalError) se asume **modo real** y se
loguea.

### Composition root

`resources/documenteme/runtime.py` → `resolve()` devuelve el bundle de
adaptadores (real o simulado). Los orquestadores no saben si se simula; piden
el bundle y lo aplican.

| Clave del bundle | Simulado |
|---|---|
| `sync_send_fn` | `simulation.build_inbound_sync_double` (fixtures) |
| `sync_tax_id_fn` | NIT simulado `999999999` |
| `approve_send_fn` | `simulation.send_purchase_invoice_request` (BC ok) |
| `event_http_fn` | `simulation.http_event` (eventos ok) |
| `company_tax_id_fn` / `event_endpoint_fn` | NIT / endpoint simulados |
| `on_batch_approved_fn` | actor de confirmación automática (`_apply_simulated_confirmation`) |
| `data` | `DataFacade(store=session.store())` |
| `approve_callbacks` | callbacks in-memory (`po_exists`, `receipt_bank_fn`, `consume_receipts_fn`, …) |
| `sync_persist` | persistencia in-memory (`documents_memory`) |

### Sesión y limpieza

- `simulation/session.py`: `store()` (lazy) / `reset()`. Cada
  `_sync_documents` en modo simulación **resetea** el store (`_resolve_sync_runtime`)
  y lo vuelve a sembrar.
- Nada se borra de la DB real; las facturas simuladas viven solo en la sesión.

---

## 2. Cómo habilitar

```bash
# Si falta la columna documenteme_simulation (doctype qp_SP_MasterSetup):
bench --site <sitio> migrate

# Toggle (solo Administrator): Desarrollador > qp_SP_MasterSetup
#   documenteme_simulation = 1
```

Con ese flag la página `/documenteme/sales_invoices` muestra el banner
`context.simulation_mode` y al cargar dispara `refresh_documents()` que corre
sync → assign → approve → reject sobre los fixtures.

---

## 3. Escenario simulado (11 facturas)

Fuente de datos: `resources/documenteme/fixtures/documenteme_fixtures.json`
(11 cabeceras + 11 detalles). Los seeds de referencia los siembra
`simulation/seeds.py:seed_scenario(store)` en el composition root simulado.

Cada factura **etiqueta su caso en `Nvpro_nomb`** (columna proveedor de la
vista) para saber qué se está probando a simple vista.

| Factura | Tipo | Datos de referencia | Estado final esperado |
|---|---|---|---|
| `SIM-FAC-0001` | Crédito sin OC | — | **R** (rechazada) |
| `SIM-FAC-0002` | Crédito sin OC | — | **R** (rechazada) |
| `SIM-FAC-0003` | Contado con OC `PO-SIM-0001` | PO | **A** (aprobada, directo sin evento) |
| `SIM-FAC-0004` | Contado sin OC | — | **E + asignada** (no aprueba: rompe `no_po`) |
| `SIM-POA-0001` | Crédito · OC `PO-A-0001` | banco A | **A** (2000 = 500+1500) |
| `SIM-POA-0002` | Crédito · OC `PO-A-0001` | banco A | **A** (4000 = 1000+3000) |
| `SIM-POB-0001` | Crédito · OC `PO-B-0001` | banco B | **A** (1000) |
| `SIM-POB-0002` | Crédito · OC `PO-B-0001` | banco B | **A** (2000) |
| `SIM-POB-0003` | Crédito · OC `PO-B-0001` | banco B | **E + asignada** (2500 no cubre) |
| `SIM-POC-0001` | Crédito · OC `PO-C-0001` | banco C | **E + asignada** (ninguno cubre) |
| `SIM-POC-0002` | Crédito · OC `PO-C-0001` | banco C | **E + asignada** (ninguno cubre) |

Seeds de referencia (mismo NIT `999999999`):

- `qp_SP_Supplier` — proveedor simulado (sin regla de rechazo propia).
- `qp_SP_MasterSetup` name `MASTER-SETUP` — `auto_approve=1`, **`auto_reject="RULE-NO-PO"`**.
- `qp_SP_AutoRejectRule` — `RULE-NO-PO` (`rule_code=no_po`), regla default activa.
- `qp_md_headquarter` — `HQ01`.
- `qp_SP_OCType` — `COMPRA` (no inventariable).
- `qp_SP_AssignmentConfig` `CFG-COMPRA` + user `asignado@sim.local` (oc_type) y **`CFG-CATCHALL`** (oc_type/headquarter vacíos = destinatarios por defecto del contado sin OC).
- POs: `PO-SIM-0001`, `PO-A-0001`, `PO-B-0001`, `PO-C-0001` (headquarter `HQ01`).
- Recibos `qp_SP_PurchaseReceipt` con `total`/`posting_date`/`qp_invoice=''`/`supplier_delivery_note`:
  - **Banco A** (PO-A-0001): `REC-A-1=500`, `REC-A-2=1500`, `REC-A-3=1000`, `REC-A-4=3000` → **caso A: consistente, aprueban todas**.
  - **Banco B** (PO-B-0001): `REC-B-1=1000`, `REC-B-2=2000`, `REC-B-3=1000` → **caso B: parcial, aprueban solo las cubiertas** (2500 no es combinable).
  - **Banco C** (PO-C-0001): `REC-C-1=500`, `REC-C-2=700` → **caso C: ninguna factura cubre ninguna recepción** (1000 y 800 no combinables).
- Items (child tables): `qp_SP_PurchaseOrderItem` (por PO) y `qp_SP_PurchaseReceiptItem` (por recibo) para la vista (detalle de OC/recibos).

> Los seeds son **idempotentes** (insert-if-missing): al re-resolverse el
> composition root dentro del mismo sync **no** pisan el estado mutado de los
> recibos (`qp_invoice` ya consumido). Se aplican en `_resolve_sync_runtime`
> (al sincronizar), no en cualquier `resolve()`.

### Cómo termina cada factura (flujo real in-memory)

`_sync_documents` (y `_launch_reject` al final) encadenan:

1. **Sync** (fases 1-2) → 11 documentos en `E`.
2. **Auto-assign** (`simulation/assign_memory.py`, con la regla `no_po`
   resuelta del MasterSetup) → asigna:
   - crédito con OC cuya combinación de recibos **no** la cubre
     (POB-0003, POC-0001, POC-0002);
   - **contado sin OC que rompe `no_po`** (SIM-FAC-0004) vía la fila catch-all.
   El contado con OC (SIM-FAC-0003) no se asigna (no rompe `no_po`).
3. **Auto-aprove** (`run_auto_approve`) → las elegibles pasan `E→V→BCC→A`:
   - Contado con OC (0003): `A` directo sin eventos, `nvfac_ueve` vacío,
     `qp_is_event_completed=1`. El contado sin OC (0004) **no sube a `V`**
     (advertencia "debe asignarse" por `no_po`).
   - Crédito cubierto: confirmación automática → eventos 030/032/033 → `A` con
     `nvfac_ueve='033'` y `factura_interna` (`SIMCONF-...`).
4. **Auto-rechazo** (`simulation/reject_memory.py`, **rule-driven**: la regla
   activa decidida por `memory_resolve_rule`) → el crédito sin OC bajo `no_po`
   (SIM-FAC-0001/0002) termina en `R` con eventos 030/032/031. El contado
   **nunca** se auto-rechaza (va a aprobación/asignación).

Estado final: `R`×2, `A`×5, `E asignada`×4.

---

## 4. Adaptadores (referencias y config) y punto de decisión

La vista enriquece `ordenes_compra` / `recepciones` / `productos_*` a través
de un **adaptador inyectable** (las referencias NO se consultan con doctype
hardcodeado):

- Contrato implícito (Python 3.6, sin ABC): `po_exists`, `po_items`,
  `receipts_for`, `receipt_bank_for`, `receipt_items_for`.
- `infrastructure/adapters/reference_source.py` → **`RealReferenceSource`**
  (frappe): `Purchase Order` / `Purchase Receipt` (+ child) — modo real intacto.
- `simulation/reference_source.py` → **`MemoryReferenceSource`** (store):
  tablas en memoria `qp_SP_PurchaseOrder` / `qp_SP_PurchaseReceipt` (+ items).
- `DataFacade` expone `.references` → la vista (que ya usa el facade) resuelve
  el adaptador sin cambiar call-sites. `services/enrich_document_detail.py` /
  `enrich_document_list.py` aceptan `references` opcional (default = real).

Con esto, en simulación la vista muestra la OC, sus productos y —**solo**—
los recibos asignados/procesados con la factura (badges con
`supplier_delivery_note`) y sus productos, igual que en modo real. La
asignación de recibos a una factura la hace el flujo de aprobación
(`consume_receipts_fn` marca `qp_invoice = nvfac_nume` en los recibos
emparejados); la vista filtra con `receipts_for(po, qp_invoice=nvfac_nume)`,
de modo que los recibos de la OC que **no** forman parte de la factura no se
muestran.

### Adaptador de configuración del MasterSetup

La config del escenario (`auto_approve`, `auto_reject`, reintentos) se lee a
través de `DataFacade.master_setup`:

- `infrastructure/adapters/master_setup_source.py` → **`RealMasterSetupSource`**
  (frappe; args/fallbacks idénticos a las lecturas anteriores) y helper
  `resolve_master_setup_source(data, frappe_module)`.
- `simulation/master_setup_source.py` → **`MemoryMasterSetupSource(store)**:
  lee la fila sembrada `qp_SP_MasterSetup`; si el campo no está sembrado
  devuelve `None`/default, **nunca** frappe.
- Consumidores: `auto_approve.is_auto_approve_enabled`,
  `auto_reject.get_reject_config`/`get_setup_default_rule`/`resolve_rule`,
  `auto_approve_confirmation.get_approval_config` aceptan `master_setup` opcional
  (default = Real con el `frappe` de su propio módulo).
- Las reglas en memoria se resuelven con `references_memory.memory_resolve_rule`
  (proveedor → default MasterSetup → `qp_SP_AutoRejectRule`), usada por
  `promote_eligible_to_v`, `assign_memory` y `reject_memory`.

### Independencia real ↔ simulador

La decision simulado/real vive **solo** en `resources/documenteme/runtime.py`:
`is_simulation_enabled()` lee `qp_SP_MasterSetup.documenteme_simulation` de la
DB real (tolerante: ilegible ⇒ `False`) y `resolve()` entrega el bundle
(`_simulated_bundle` / `_real_bundle`). Consumidores no deciden: usan
`runtime.resolve().get("data")` (`None` en real → frappe directo).

Garantías de independencia:

1. `documenteme_simulation` **queda fuera del adaptador** (no es config de
   escenario; es el switch operativo).
2. En real, `data` no existe → los consumidores usan el adaptador Real (frappe
   de su módulo) → jamás leen el store/seeds.
3. En sim, `MemoryMasterSetupSource`/`MemoryReferenceSource` leen SOLO el store;
   los campos no sembrados dan `None`/default → la simulación no se contamina
   con la config real.
4. El store se resetea/siembra en `_resolve_sync_runtime` del sync simulado
   (nunca en un `resolve()` cualquiera).

---

## 5. Módulos clave de la simulación

| Archivo | Rol |
|---|---|
| `resources/documenteme/runtime.py` | Composition root: **única decisión** sim/real (`is_simulation_enabled` + `resolve`); bundle con `resolve_rule_fn=memory_resolve_rule` |
| `resources/documenteme/simulation.py` | Doubles (inbound sync, BC, eventos, confirmación) + `load_fixtures` |
| `resources/documenteme/fixtures/documenteme_fixtures.json` | 11 facturas del escenario |
| `simulation/session.py` | MemoryStore de sesión (`store()` / `reset()`) |
| `simulation/store.py` | Motor de query in-memory compatible Frappe |
| `simulation/seeds.py` | `seed_scenario(store)` idempotente (supplier, regla, MasterSetup, sede, OCType, assignment, POs, recibos, items) |
| `simulation/documents_memory.py` | Persistencia in-memory (sync, approve, confirmación, consume recibos) |
| `simulation/references_memory.py` | Referencias in-memory (PO, receipt bank, sede, supplier, users) + **`memory_resolve_rule`** (regla activa) |
| `simulation/assign_memory.py` | Auto-assign in-memory (núcleo puro `auto_assign`, con regla resuelta del MasterSetup) |
| `simulation/reject_memory.py` | Auto-rechazo in-memory **rule-driven** (030/032/031; contado nunca se rechaza) |
| `simulation/reference_source.py` / `infrastructure/adapters/reference_source.py` | `MemoryReferenceSource` / `RealReferenceSource` (vista: OC/recibos) |
| `simulation/master_setup_source.py` / `infrastructure/adapters/master_setup_source.py` | `MemoryMasterSetupSource` / `RealMasterSetupSource` (config del escenario) |
| `infrastructure/adapters/data_facade.py` | `DataFacade` (memoria/real) con `.references` y `.master_setup` |
| `uses_cases/documents/sync_all_whitelist.py` | Cableado: `_resolve_sync_runtime` (reset + seeds), memory-`run_documenteme_auto_assign`, `_launch_reject` |

Detalle del banco de recibos (emparejamiento de recepciones por OC): ver
`docs/BANCO-RECIBOS.md`.

---

## 6. Tests

Correr **cada archivo por separado** con el python del bench (flakes por
contaminación of `frappe=MagicMock()` entre archivos son conocidos):

```bash
cd <bench>
env/bin/python -m unittest qp_supplier_front.tests.<archivo> -v
```

| Test | Cubre |
|---|---|
| `test_sim_sync_in_memory` | Sync fases 1-2 → 11 docs `E` sin DB real |
| `test_sim_auto_approve_in_memory` | Auto-aprobación contado in-memory (sin regla → aprueba) |
| `test_sim_assign_in_memory` | Asigna crédito no-cubierta y contado sin OC (rompe `no_po` → catch-all); los demás no |
| `test_sim_scenario_in_memory` | Escenario completo: estados finales R×2/A×5/asignada×4, consumo de recibos, vista OC/recibos |
| `test_sim_reject_in_memory` | Rechazo rule-driven (crédito sin OC → R; contado nunca) |
| `test_sim_reference_source` | `MemoryReferenceSource` (PO, recibos, bank, items) + `facade.references` |
| `test_sim_master_setup_source` | `MemoryMasterSetupSource`/`RealMasterSetupSource` + independencia real↔sim |
| `test_sim_approve_in_memory` / `test_sim_view_in_memory` | Aprobar in-memory / vista (paginación, enrich, acceso) |
| `test_receipt_bank` | Núcleo puro del banco de recibos (incluye emparejar por `nvfac_stot`) |
| `test_documents_memory` / `test_data_facade` / `test_documenteme_runtime` / `test_documenteme_simulation(_scenarios)` | Capa in-memory y composition root |

> Sin cambios de doctype en este escenario → **no requiere `bench migrate`**
> (solo si se agrega la columna `documenteme_simulation` al doctype por
> primera vez).

---

## 7. Notas operativas

- `data_facade._Real.get_all/get_list` deben reenviar `pluck`/`start`/`page_length`
  a `frappe.*` (regresión ya corregida; no volver a romperla).
- El contado finalizado (A/R) tiene `nvfac_ueve` vacío (no notifica DIAN); eso
  NO es "en cola" — `qp_is_event_completed=1` es la señal de completado local.
- `reject_memory` es **rule-driven** (usar `memory_resolve_rule`): sin regla
  activa no rechaza; el contado nunca se auto-rechaza (va a aprobación/asignación).
- El adaptador de MasterSetup NO expone `documenteme_simulation` (sigue siendo
  el gate real); independencia garantizada por diseño (ver §4).
- No tocar `taks/sync.py` (LEGACY) ni los shims `sales_order/`, `receipts/`.