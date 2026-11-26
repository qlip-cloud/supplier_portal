# documenteme: detalle de factura con muchas OC y recepciones

Objetivo: que una factura con decenas de OC y recepciones no genere una lista eterna ni cientos de consultas, manteniendo la seleccion manual de recibos disponible.
Rama: develop-documenteme. Estrategia de entrega: ask-on-risk. Runner: `/workspace/development/mentum_localhost/env/bin/python -m pytest` (tests unitarios con frappe mockeado).

## Specs

- S1 — La cabecera de la fila no crece sin limite: la celda "Orden de compra" y los badges de "Recepción" muestran como maximo 3 elementos y un indicador "+N" con el listado completo en el tooltip (`title`).
- S2 — Detalle inline: si la factura tiene como maximo 3 OC y 10 recepciones se renderiza igual que hoy (productos y banco seleccionable). Si supera alguno de los dos limites, la fila muestra solo un resumen (cantidad de ordenes, cantidad de recepciones, montos libres y reclamados) y un boton "Ver detalle".
- S3 — Modal "Ver detalle" con dos pestanas: "Ordenes" (tabla con numero, fecha, tipo, sede, total, cantidad de recibos; fila expandible con productos) y "Recepciones" (banco completo con checkboxes, buscador, grupos por OC colapsables y barra Aplicar/suma/clasificacion visible).
- S4 — "las recepciones ... PUEDES HACER selecciones manuales asi q tienen q estar dispobiles": las recepciones siguen siendo seleccionables y aplicables desde el modal. Al aplicar se cierra el modal y se refresca solo la fila afectada.
- S5 — La factura anomala no dispara cientos de consultas: la validacion de OC y la lectura de recibos se hace en una consulta cada una; los productos se traen recien al abrir el modal. El listado de 15 filas no llama `po_items`, `receipt_items_for` ni `bank_for_invoice` por cada OC cuando la factura es grande.
- S6 — Sin regresion para facturas normales (dentro de los limites): mismo HTML inline, misma logica de seleccion y aplicacion, mismos tests existentes.
- S7 — Modo simulacion: el endpoint del modal usa el bundle real/simulado igual que el resto del flujo; los adaptadores in-memory mantienen el contrato de referencias.

## Tasks

- T1 — Partiales `_oc_groups.html` y `_receipt_bank.html`; `row.html` con truncado de cabecera, resumen y botones. inline. hecho.
- T2 — `enrich_document_detail`: limites, modo resumen, totales; `enrich_document_list` con `include_products`. inline. hecho.
- T3 — Adaptadores: metodos batch `po_belongs_to_supplier_many`, `po_items_many`, `receipts_for_many`, `bank_for_invoice_many` (Real y Memory); `get_bank_for_orders` en `receipt_claim_adapter`. inline. hecho.
- T4 — Endpoint `resources/documenteme/invoice_detail.get_detail` + templates del modal. inline. hecho.
- T5 — JS (modal, pestanas, buscador, aplicar) y CSS. inline. hecho.
- T6 — Tests nuevos y ajuste de `test_enrich_document_list` (firma con `include_products`). inline. hecho.
- T7 — Verificacion: pytest de los archivos tocados. inline. hecho.

## Evidencia de verificacion

- `pytest test_documenteme_detail_limits.py`: 6 passed (limites, batch, respaldo, totales libres/reclamados).
- `pytest` de `test_enrich_document_detail`, `test_enrich_document_list`, `test_double_oc`, `test_receipt_bank_gates`, `test_sim_reference_source`, `test_sim_view_in_memory`, `test_sim_scenario_in_memory`, `test_sim_approve_in_memory`, `test_sim_auto_approve_in_memory`, `test_sim_reject_in_memory`, `test_sim_sync_in_memory`, `test_sim_notifications_in_memory`, `test_documenteme_runtime`: todos verdes.
- `test_data_facade::TestRealFacade::test_get_v_doc_names_real_devuelve_strings` falla por falta de contexto de sitio (frappe session sin bind); no toca los archivos modificados.
- Smoke de templates con Jinja standalone: `row.html` (limitado y completo) y `invoice_detail_body.html` renderizan; en modo limitado no aparece `.receipt-bank` (sin ids duplicados) y aparece `+N`.
- `node --check index.js`: OK.

## Log

### L1 (original)
se presento el caso en documenteme q un usuario asigno 65 ordenes a una factura, ya corregimos el  error del campo de control pero no la desconfiguracion en el front de mostrar 65 facturas se hace una lista eterna, deberiamos mostrar un paginador o un modal q las muestre todas analiza esa mejora

### L2
las oc no seral el problema tambien la lista de recepciones q pueden llegar hasta ser el doble hay q aplicarlo a los dos, pero las recepciones dan un problema exrA Y ES Q PUEDES HACER selecciones manuales asi q tienen q estar dispobiles, no estoy claro cual sea la mejor opcion

### L3
aplica lo recomendado para verlo

### Analisis
- El acordeon se renderiza server-side aunque este cerrado (`row.html:97`) y la pagina trae 15 filas (`services/pagination.py:7`).
- Una fila con 65 OC dispara ~390-400 consultas por el fan-out por OC de `enrich_document_detail`.
- El banco de recepciones ya esta scopeado por `.receipt-bank[data-doc][data-stot]` y con handlers delegados en `document` (`index.js`), por lo que el mismo markup funciona dentro de un modal.
- El collapse anidado usa `id="receipt-products-<name>"`: renderizar el mismo recibo en fila y modal generaria ids duplicados. Se usa un solo host (inline o modal, nunca ambos).
- Se descarta el paginador dentro de la columna: la seleccion manual necesita comparar montos y disponibilidad y el paginador reparte el estado entre paginas sin buscador.

### Ajustes de revision (post-implementacion)
- "Valor total" alineado a la derecha en las tres tablas del detalle (factura, OC y productos de recepcion), como columna monetaria; "Valor unitario" queda igual (derecha). Se usa estilo inline para no depender del cache del CSS externo.
- Al aplicar una recepcion desde el modal: se cierra el modal y el resultado se muestra como alerta flotante (`frappe.show_alert`), sin modal ni backdrop. Antes el `msgprint` se abria con el modal visible y su backdrop quedaba por debajo.
- `no_cache = 1` a nivel de modulo en `www/monitor/documenteme/index.py`: Frappe inyecta `index.js` como `colocated_js` en el HTML y, en sitios con `developer_mode=0`, cachea el `page_context` (incluido ese JS) en Redis; esto evita que los cambios de JS queden pegados hasta un `clear-cache`.
- Nota operativa: la pagina inyecta el JS dentro del HTML, asi que para ver cambios de JS hay que recargar (Ctrl+Shift+R); el proceso de `frappe serve` corre con `--noreload` y los cambios de Python requieren reinicio.
