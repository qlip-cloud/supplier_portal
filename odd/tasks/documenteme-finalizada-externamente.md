# Cerrada (FE) — documenteme

Branch: `develop-documenteme`. Delivery: ask-on-risk. Tests: `python -m pytest` (archivo por archivo).

Factura registrada en el portal que se resolvió fuera del sistema: se cierra en un estado local `FE` sin crear en BC/GP ni notificar a documenteme, y queda inmutable (sin cambios de estado ni sync). Solo `Administrador Documenteme` / `Administrator` pueden cerrar y reabrir, con motivo obligatorio.

## Specs

- **S1**: "hay ocaciones en donde una factura la tenemos registrada en nuestro sistema pero esa factura fue resuelva fuera de nuestro sistema, debemos darla la posibilidad al usuario de cerrar la factura sin generar creacion en bc ni notificar a dopcumenteme seria como un estado de Finalizada externamente".
- **S2**: "si una factura es marcada como fe sesa toda interaccion, no se puede cambiar de estado, ni sincronizar ni nada".
- **S3**: "este tipo de acciones son propensas a errores asi q puede pasar el administrador documenteme podria habilitarla" ⇒ reapertura break-glass con motivo.
- **S4**: "esta es una opcion q solo tendra el administrador documenteme y el administrador".
- **S5**: "colocale el boton de cerrar y si tiene ese estado el reabrir, con el modal del motivo".
- **S6**: motivo obligatorio en cerrar y en reabrir; auditoría persistida (quién, cuándo, por qué, estado previo).
- **S7**: al cerrar no se aprueba, rechaza, asigna, aplican recibos, comentan ni programa ningún evento 030/032/031/033.
- **S8**: el sync no toca una FE: ni estado, ni `nvfac_ueve`, ni historial, ni re-descarga de detalle.
- **S9** (supersede parcialmente S2): "el usuario deberia poder dejar comentarios en observaciones" aunque la factura esté cerrada; comentar no es una mutación del flujo. El ícono de observaciones queda siempre visible y el timeline escribe por child insert directo (no `save()` del padre).

## Decisiones

- **D1**: código de estado `FE`; `nvfac_esta` es `Data` (sin options de doctype).
- **D2**: estados de origen permitidos: `E`, `V`, `T`, `SO`, `SR`, `PSA`. Bloqueados: `BCC`, `PA`, `PR`, `A`, `R`, `FE`.
- **D3**: roles: `can_see_all_documenteme` (Administrator + Administrador Documenteme). Administrador Sede/Compras quedan fuera.
- **D4**: inmutabilidad en tres capas: `notification_state.is_locked`, early returns del sync y `validate` global que rechaza cualquier `save()` de un FE (salvo reapertura marcada con `doc.flags.allow_external_reopen`).
- **D5**: al cerrar se copia `qp_external_previous_state`; reabrir restaura ese estado y pone `qp_is_event_completed = 0`.
- **D6**: la reapertura no borra la auditoría del cierre; el motivo de reapertura queda en el timeline.
- **D7**: UI por fila en la columna de acciones: candado cerrado rojo (`lock`) para cerrar, candado abierto verde (`lock_open`) para FE (abre auditoría + reabrir). Sin acción masiva.
- **D8**: comentarios permitidos en FE; solo se bloquean mutaciones del flujo (aprobar, rechazar, asignar, recibos, OC, referencia NC, adjuntos del registro, re-sync).

## Tasks

- [x] T1 Núcleo del estado (S2, S7) — inline.
- [x] T2 Guardas de sync (S2, S8) — inline.
- [x] T3 Exclusiones de flujos automáticos (S2, S7) — inline.
- [x] T4 Auditoría + hook de inmutabilidad (S2, S6) — inline.
- [x] T5 Endpoints cerrar/reabrir/status (S1, S3, S4, S6) — inline.
- [x] T6 Front botones + modales (S5) — inline.
- [x] T7 Tests (S1-S8) — inline.

## Log

- **L1**: "analiza el siguiente flujo para bc / hay ocaciones en donde una factura la tenemos registrada en nuestro sistema pero esa factura fue resuelva fuera de nuestro sistema, debemos darla la posibilidad al usuario de cerrar la factura sin generar creacion en bc ni notificar a dopcumenteme seria como un estado de Finalizada externamente, analiza todo el flujo para poder realizar esta feat".
- **L2**: "si una factura es marcada como fe sesa toda interaccion, no se puede cambiar de estado, ni sincronizar ni nada".
- **L3**: "este tipo de acciones son propensas a errores asi q puede pasar el administrador documenteme podria habilitarla pero pienso mas en donde ubicar los botones".
- **L4**: "esta es una opcion q solo tendra el administrador documenteme y el administrador, colocale el boton de cerrar y si tiene ese estado el reabrir, con el modal del motivo".

- **L5** (implementacion): T1-T7 implementadas inline. Archivos nuevos: `uses_cases/documenteme/finalize_external.py`, `resources/documenteme/finalize_external.py`, `resources/documenteme/immutability.py`, `templates/modal/external_close.html`, `tests/test_finalize_external.py`. Hook `validate` en `hooks.py`. Campos de auditoria en `qp_sp_documentdetail.json`.
- **Evidencia**: `python -m unittest qp_supplier_front.tests.test_finalize_external` -> 26 OK. Tests existentes relevantes (notification_state, document_sync, documents_memory, timeline, receipt_selection, assign_infra) OK. Fallos preexistentes por entorno (sin `requests`/`jinja2`) no relacionados.
- **Pendiente operativo**: `bench --site <sitio> migrate` (campos), `bench restart` (hook) y `bench build` (front). Sin commit (no solicitado).
- **L6**: "el usuario deberia poder dejar comentarios en observaciones..., cambia el icono de cerrar a un candado rojo cerrado, y reabrirlo un candado abierto verde".
- **L7** (implementacion): comentarios habilitados en FE (se retira el bloqueo de `add_comment` y el modo solo-lectura del timeline); iconos ajustados (`lock` rojo para cerrar, `lock_open` verde para reabrir). Tests `test_finalize_external` + `test_timeline`: 58 OK.
