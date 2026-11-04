# BC credit note (qp_SP_DocumentDetail.nvtip_docu="C")

Branch: develop-notested. Delivery: ask-on-risk. Tests: python -m unittest (per file).

## Specs

- S1: Incorporate NC handling for the BC backend ("debemos incorporar el manejo de nc para bc").
- S2: Reuse the GP reference-invoice selection philosophy ("vamos a utilizar la misma filosofia de seleccion de referencia para la nota de credito").
- S3: Send the NC with the unified `create_purchase_noreceipt` shape: `DocumentType: "Credit Memo"`, `invoiceDate`, `postingDate`, `vendorNumber`, `puntofacturacion: ""`, `NoFacturaProveedor` (= NC number `nvfac_nume`), `tipoFacturaDoc: ""`, `Categoria`, `SubCategoria`, `Cufe`, `Almacen`, `formaPago`, `NoFacturaAfectada`, `dimensionSetLines` (`TERCERO`), lines with `NoProducto`, `cantidad`, `Precio`, `Type` hardcoded `"Item"`, `Comentarios`.
- S4: endpoint_code = `create_purchase_noreceipt` para la NC (mismo servicio/JSON que las facturas sin OC). `create_purchase_nc` queda configurado pero sin uso.
- S5: `NoFacturaAfectada` is the BC `confirmation_id` of the reference (`qp_SP_PurchaseInvoiceBC.confirmation_id`, ej. `FC70071`).
- S6: `NoProducto`, `cantidad` y `Precio` salen de las lineas de recepcion/OC de la factura referencia ("NoProducto: se usa la recepcion / oc de la factura referencia"). En BC no se usa homologacion. Pedido de negocio: se envian las lineas de la recepcion tal cual (dos recepciones del mismo item = dos lineas), sin consolidar. Observacion: la alternativa por linea de NC queda en `credit_note_bc.resolve_credit_note_lines`.
- S7: Mixed approval batch (invoices + NC) is allowed because it is the same service ("si es el mismo servicio").
- S8: BC service-supplier NC is out of scope ("no el proceso de bc es distinto").
- S9: BC does not use the GP devolution bank ("no tiene nada q ver con gp").
- S10: Reference candidates are only BC invoices ("solo de bc").
- S11: The endpoint returns the same semicolon-separated response contract with the BC document number.
- S12: Middleware changes are isolated from the documenteme purchase-invoice flow ("es un proceso aislado del proceso de documenteme confirma q no interfiere").

## Tasks

- [x] T1 (S1-S6, S8-S10) BC NC lines + payload builder: `get_lines_bc_nc`, credit-note resolver, `_build_credit_note`. Route: inline. Files: `uses_cases/documenteme/credit_note_bc.py`, `resources/documenteme/_approve_base.py`, `uses_cases/documenteme/approve.py`.
- [x] T2 (S4, S7, S11, S12) Endpoint routing + grouped batch send in the shared core; BC send dispatch. Route: inline. Files: `constant/endpoint.py`, `uses_cases/documenteme/approve.py`, `resources/documenteme/_approve_base.py`. Single-endpoint path preserved byte-for-byte.
- [x] T3 (S5, S10) Backend-aware reference candidates/validation (`nc_reference.py`). Route: inline.
- [x] T4 (S12, S4) Middleware `create_credit_notes` (new module, additive; `create_purchase_invoices` untouched). Route: inline (other repo `qp_middleware`).
- [x] T5 (all) Tests: pure resolver, builder, grouped send, middleware validation/response. Route: inline. `test_bc_credit_note` (11), `test_credit_note_sync` (8), existing suites green.

## Verification

- `python -m unittest qp_supplier_front.tests.test_bc_credit_note` → 11 OK.
- `python -m unittest qp_supplier_front.tests.test_approve` → 136 OK.
- `python -m unittest qp_supplier_front.tests.test_auto_approve` → 30 OK.
- `python -m unittest qp_supplier_front.tests.test_sim_approve_in_memory` / `test_sim_gp_approve_in_memory` / `test_sim_gp_documenteme_in_memory` → OK.
- `python -m unittest qp_middleware...test_purchase_invoice_sync ...test_credit_note_sync` → 43 OK (frappe/requests from bench env python).
- Known pre-existing failure (verified against pristine `git archive HEAD` in /tmp): `tests/characterization/test_characterization_approve_payload.py` (stale golden lacking `Categoria`/`SubCategoria`). Not caused by this change.

## Operational step (not code)

- `create_purchase_noreceipt` must exist with the unified `soap_template` (it does on davita.qa). `create_purchase_nc` is still configured on davita.qa (`Codeunit/CrearNotaCreditoCompra`) but the NC no longer uses it.

## Log

- L1: "debemos incorporar el manejo de nc para bc / en gp hay una funcionabilidad para elegir la factura de referencia para anadirla al crearla en gp / vamos a utilizar la misma filosofia de seleccion de referencia para la nota de credito / este es el payload q debemos usar" + SOAP `FacturasNCCompraWS` with endpoint_code `crear_nota_credito_compra`.
- L2: "NoFacturaAfectada: el numero de factura afectada es el numero de la factura referencia / NoProducto: se usa la recepcion / oc de la factura referencia / Lote mixto: si es el mismo servicio / Proveedor de servicio: no el proceso de bc es distinto / Exceso / banco de devoluciones: no tiene nada q ver con gp / Candidatas de referencia: solo de bc / Respuesta del endpoint si / Alcance del repo qp_middleware: no entiendo q tiene q ver con middleware".
- L3: User confirms BC number (`invoice_id`) is expected; line data may be taken from the reference receipt/OC as needed; middleware is an isolated process and must not interfere with documenteme.
- L4: "unificalo con el cambio del otro agente, ese cambio lo pedi yo" → final endpoint_code `create_purchase_nc` (commit `557935d`, pedido por el usuario). Se alineó el default del middleware y este documento.
- L5: "el json de nota de credito fue modificado ... este es el nuevo json por eso tienes ese cambio en develop-notested / tendrias q evaluar nuevamente el json para generar el mapeo". Nuevo payload NC: `DocumentType: "Credit Memo"`, `puntofacturacion: ""`, `NoFacturaProveedor` (= número NC), `tipoFacturaDoc: ""`, `NoFacturaAfectada` (= número BC de la referencia). Se reutiliza `_build_no_receipt_invoice` y se elimina `_build_credit_note`.
- L6: "la nota de credito usara el mismo enpoint_code create_purchase_noreceipt / crea una factura de tes, y toma las q ya existen y cambiale el proveedor a uno q si coincida / usaremos el confirmation_id". NC -> `create_purchase_noreceipt`; referencia = `confirmation_id`; datos QA preparados en davita.qa.
- L7: "para bc no es requerida la homologacion, para bc se envia los productos de las recepciones sino tiene recepciones se envia la de la orden de la factura referencia". El resolver no intenta homologar el codigo del proveedor de la NC.
- L8: "tiene q ser con las lineas de la recepcion.... pero estoy deacuerdo contigo, solo que asi lo solicitaron, hazla por la recepcion y deja la observacion por si tenemos q cambiarlo". Se envia una linea por cada linea de recepcion/OC de la referencia (con su producto, cantidad y precio). Verificado con `900162414:SETP990300032` (ref FC70073): OP0116 150@5792 y OP0116 50@2129.
