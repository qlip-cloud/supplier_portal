# documenteme-sync-all-ueve

Objetivo: registrar TODO el listado de documenteme en el portal (cualquier estado y cualquier `Nvfac_ueve`), tratar 030/032 como "en cola", reconciliar estado/ueve al re-sincronizar sin re-descargar, y arrancar la notificación desde el ueve de origen.

Branch: `feat/documenteme-sync-all-ueve` (desde `develop-documenteme`).
Delivery: work-unit commits en la feature branch. Tests: `env/bin/python -m pytest <archivo> -q`.

## Specs

- S1. El sync crea `qp_SP_DocumentSyncLine` para todos los documentos del listado, sin filtrar por `Nvfac_ueve` (vacío, 030, 031, 032 o 033).
- S2. `qp_SP_DocumentDetail.nvfac_ueve` guarda el estado de notificación tal como lo trae documenteme.
- S3. `nvfac_esta=T` trae todas: el parámetro del request no cambia y su test sigue pinneando `"T"`.
- S4. No se hace backfill: solo entra lo que devuelve el listado en su ventana.
- S5. Las facturas con `Nvfac_ueve` 030 o 032 entran al flujo igual que las de ueve vacío (asignación, promoción a V, auto-aprobación, auto-rechazo, receipt trigger).
- S6. Las facturas con `Nvfac_ueve` 031 o 033 son finales: se registran y se muestran, pero no entran al flujo automático.
- S7. La secuencia de notificación arranca desde el ueve de origen: vacío→030; 030→032; 032→033 (aprobación) / 031 (rechazo); final→sin eventos.
- S8. Re-sincronizar reconcilia el estado/ueve de la factura sin re-descargar: el origen final (A/R o 031/033) manda; un origen intermedio (030/032) respeta el estado local avanzado (SO/SR/PSA/BCC/PA/PR/A/R); un ueve final local nunca baja a 030/032.
- S9. El historial registra que el ueve vino de documenteme (`entry_by = "Documenteme"`), sin duplicados.
- S10. Sin `bench migrate`: no se agregan campos. Solo `bench build` por el JS del timeline.
- S11. Compatibilidad Python 3.6 (sin f-strings, dataclasses ni typing en firmas).
- S12. No se rompe el comportamiento existente: facturas con ueve vacío siguen fluyendo, 031/033 siguen excluidas, `nvfac_esta=T` se mantiene.
- S13. Una factura importada con estado final de documenteme (A/R) queda en `A/R` local y no es aprobable/rechazable/asignable.

## Tasks

- T1. Núcleo puro `uses_cases/documenteme/notification_state.py` + `tests/test_notification_state.py`. Spec: S2,S5,S6,S7,S8,S11,S12. Route: inline. Status: done (RED: ModuleNotFoundError; GREEN: 18 passed).
- T2. Ingesta y reconciliación (`services/document_sync.py`, `simulation/documents_memory.py`, timeline) + tests. Spec: S1,S2,S7(historial),S8,S9,S10,S13. Route: inline. Status: done (131 tests verdes; commit 320a90f).
- T3. Elegibilidad 030/032 (`auto_approve`, `auto_assign`, `auto_reject`, `receipt_trigger`, espejos de simulación) + tests. Spec: S5,S6,S12. Route: inline. Status: done (tests reales+sim verdes).
- T4. Secuencia desde el ueve de origen (`event_job`, `auto_approve_confirmation`) + tests. Spec: S7,S12. Route: inline. Status: done (event_job + simulacion; 73 tests verdes).
- T5. Etiqueta del timeline en el front + documentación (SKILL/AGENTS/docs). Spec: S9,S10. Route: inline. Status: pending.

## Log

- L1 (solicitud original, verbatim): "debemos analizar el siguiente feature: para el proceso de notificacion de documentme estamos filtrando solo los documentos Nvfac_ueve con null pero ya en produccion nos dimos cuentas de varias cosas que no funcionan bien 1.- q todas las facturas o la mayoria tienen "Nvfac_ueve": "030", parece ser q documenteme le coloca ese estatus por defecto, dejando inutilizable nuestra logica 2.- que para efectos de nc es posible q la factura a la q se hace referencia ya tenga un status A en documenteme y no la traemos porq estamos limitando a estatus E esto nos lleva a cambiar la forma de sincronizar 1.- debemos registrar todas las facturas para tenerlas en el portal ya sea o no estado E y es estatus de notificacion sea distinto de null 2.- las facturas q vengan con "Nvfac_ueve": "030" o 032 entran en el flujo ifual q las null, tomando en cuenta q su proceso de notificacion empieza desde el Nvfac_ueve q traen de documenteme, tambien se debe registrar el stado del Nvfac_ueve como lo hacemos actualmente para q se registre en el historial indicando q ese valor lo trajo desde documenteme y no fue una peticion hecha por nosotros evalúa el impacto de estos cambios antes de realizar cualquier programación".
- L2 (decisiones del usuario): no se hará backfill; foco en sincronizar todas las facturas y en el estado de notificación 030. `nvfac_esta=T` trae todas. Se aprueba la reconciliación en re-sync (nivel 1, sin re-descarga) con la regla "final de origen manda, intermedio respeta el estado local avanzado". Historial vía timeline (sin migrate). NC queda fuera de alcance (no se extiende la referencia).
