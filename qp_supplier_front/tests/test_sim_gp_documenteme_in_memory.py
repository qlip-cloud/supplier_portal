# -*- coding: utf-8 -*-
"""
test_sim_gp_documenteme_in_memory.py
====================================
Aprobacion simulada del flujo documenteme con backend GP (100% en memoria).

Con el flag documenteme_simulation activo y backend="GP", approve_documents_core
usa:
- get_lines_gp_fn (memoria): homogeniza y consolida las lineas de la factura
  contra la OC (tipo 2), o homogeniza siempre (tipo 3 proveedor servicio).
- build_invoice_fn GP: resuelve tipoFacturaDoc (1/2/3) y las fechas de la OC
  (transaction_date/schedule_date) por documento.
- persist_invoice en memoria con qp_sync_flow="GP" y BCC -> A via confirmacion.

Escenarios observados:
- Proveedor normal con OC sin recepciones -> tipo 2: las lineas salen de la
  factura homologada y consolidada contra la OC (cantidad/monto de la factura,
  idx de la OC, noRecepcion = numeroPord, noPedido vacio).
- Proveedor servicio (qp_is_service_supplier) -> tipo 3.

Ejecutar con: python -m unittest qp_supplier_front.tests.test_sim_gp_documenteme_in_memory -v
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules["frappe"] = MagicMock()

from qp_supplier_front.resources.documenteme import (  # noqa: E402
    _approve_base,
)
from qp_supplier_front.simulation import (  # noqa: E402
    seeds,
    session,
)
from qp_supplier_front.simulation.store import MemoryStore  # noqa: E402


def _seed_doc(store, nit=seeds.GP_SIM_NIT, nume="FAC-GP-0001",
              name=None, nvfac_conv="1", nvfac_orde="GP-PO-0001",
              total=3000.0, nvtip_docu="FAC"):
    name = name or "{}:{}".format(nit, nume)
    store.insert("qp_SP_DocumentDetail", {
        "name": name,
        "nvfac_nume": nume,
        "nvpro_ndoc": nit,
        "nvfac_fech": "2026-09-15 10:00:00",
        "nvfac_cufe": "CUFE-GP",
        "nvtip_docu": nvtip_docu,
        "nvfac_fpag": "",
        "nvfac_orde": nvfac_orde,
        "nvfac_rece": "",
        "nvfac_totp": total,
        "nvfac_esta": "V",
        "nvfac_ueve": "",
        "nvfac_conv": nvfac_conv,
        "nvmon_codi": "COP",
        "nvfac_stot": total,
        "nvfac_viva": 0,
        "nvpro_nomb": "PROVEEDOR GP",
    })
    return name


NC_XML_TPL = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<CreditNote xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:'
    'CommonAggregateComponents-2" xmlns:cbc="urn:oasis:names:specification:'
    'ubl:schema:xsd:CommonBasicComponents-2">'
    '<cac:BillingReference><cac:InvoiceDocumentReference>'
    '<cbc:ID>{}</cbc:ID>'
    '</cac:InvoiceDocumentReference></cac:BillingReference>'
    '</CreditNote>'
)


def _seed_nc_doc(store, reference, pi_gp_tipo, nume="NC-GP-0001",
                 purchase_order=None, bank_qty=None,
                 confirmation_id=None):
    nit = seeds.GP_SIM_NIT
    name = "{}:{}".format(nit, nume)
    pi_name = "{}:{}".format(nit, reference)
    store.insert("qp_SP_DocumentDetail", {
        "name": name,
        "nvfac_nume": nume,
        "nvpro_ndoc": nit,
        "nvfac_fech": "2026-09-15 10:00:00",
        "nvfac_cufe": "",
        "nvtip_docu": "C",
        "nvfac_fpag": "",
        "nvfac_orde": "",
        "nvfac_rece": "",
        "nvfac_totp": 0,
        "nvfac_esta": "V",
        "nvfac_ueve": "",
        "nvfac_conv": "2",
        "nvmon_codi": "COP",
        "nvfac_stot": 0,
        "nvfac_viva": 0,
        "nvpro_nomb": "PROVEEDOR GP",
    })
    store.insert("qp_SP_DocumentAttach", {
        "parent": name,
        "parenttype": "qp_SP_DocumentDetail",
        "file_name": "NC.xml",
        "file_type": "XML",
        "file_url": "NC.xml",
        "file_content": NC_XML_TPL.format(reference),
    })
    store.insert("qp_SP_PurchaseInvoice", {
        "name": pi_name,
        "invoice_id": reference,
        "status": "Abierto",
        "qp_status": "BCC",
        "qp_sync_flow": "GP",
        "gp_tipo_factura_doc": pi_gp_tipo,
        "nvfac_nume": reference,
        "purchase_order_id": purchase_order or "",
        "creation": "2026-09-10 10:00:00",
        "modified": "2026-09-10 10:00:00",
    })
    # La factura de referencia (en el flujo GP) queda con una
    # qp_SP_PurchaseInvoiceBC cuyo confirmation_id usa la NC tipo 5 con
    # referencia tipo 2 como numero de recepcion.
    store.insert("qp_SP_PurchaseInvoiceBC", {
        "invoice_id": reference,
        "purchase_invoice": pi_name,
        "confirmation_id": confirmation_id or "",
    }, name=reference)
    if purchase_order and bank_qty:
        if pi_gp_tipo == 2:
            store.insert("qp_SP_PurchaseOrderItem", {
                "name": "{}:LINE".format(purchase_order),
                "parent": purchase_order,
                "parenttype": "Purchase Order",
                "item_code": "ITEM-GP-1",
                "qty": bank_qty,
                "idx": 3,
                "uom": "UN",
            })
        else:
            store.insert("qp_SP_PurchaseReceipt", {
                "name": "REC-{}".format(reference),
                "qp_supplier_oc": purchase_order,
                "total": bank_qty,
                "posting_date": "2026-09-01",
                "qp_invoice": reference,
            })
            store.insert("qp_SP_PurchaseReceiptItem", {
                "name": "REC-ITEM-{}".format(reference),
                "parent": "REC-{}".format(reference),
                "parenttype": "Purchase Receipt",
                "item_code": "ITEM-GP-1",
                "qty": bank_qty,
                "idx": 5,
                "uom": "UN",
            })
    return name


def _seed_detail_line(store, name, codi, qty, valo):
    store.insert("qp_SP_DetailLine", {
        "parent": name,
        "parenttype": "qp_SP_DocumentDetail",
        "nvpro_codi": codi,
        "nvdet_tcan": qty,
        "nvdet_valo": valo,
    })


class TestSimGpDocumentemeInMemory(unittest.TestCase):

    def setUp(self):
        session.reset()
        self.store = MemoryStore()
        seeds.seed_gp_scenario(self.store)
        self.addCleanup(session.reset)

    def _run(self, doc_names, send_request_fn=None):
        with patch.object(_approve_base.runtime, "is_simulation_enabled",
                          return_value=True), \
             patch.object(_approve_base, "frappe", MagicMock()), \
             patch("qp_supplier_front.simulation.session.store",
                   return_value=self.store):
            return _approve_base.approve_documents_core(
                doc_names, backend="GP",
                send_request_fn=send_request_fn,
            )

    def test_tipo2_envia_lineas_consolidadas_contra_oc(self):
        name = _seed_doc(self.store)
        # La factura declara parcial del item 1 (85) y completo del item 2.
        _seed_detail_line(self.store, name, "SUP-1", 85, 31.58)
        _seed_detail_line(self.store, name, "SUP-2", 40, 12.0)

        calls = {"payload": None}

        def send_request_fn(endpoint_code, payload):
            calls["payload"] = payload
            docs = []
            for idx, invoice in enumerate(payload or []):
                docs.append({
                    "doc_number": "SIMGP{}".format(
                        invoice.get("noFacturaProveedor")),
                    "error": "",
                })
            return {"Result": 0, "invoices": docs}, 200

        result = self._run([name], send_request_fn=send_request_fn)

        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(result["errors"], [])

        invoice = calls["payload"][0]
        self.assertEqual(invoice["tipoFacturaDoc"], 2)
        self.assertEqual(invoice["noFacturaProveedor"], "FAC-GP-0001")
        self.assertEqual(invoice["cufe"], "")
        self.assertEqual(invoice["descripcion"], "FAC-GP-0001")
        self.assertEqual(invoice["numeroPord"], "GP-PO-0001")
        self.assertEqual(invoice["moneda"], "COP")
        # Fechas de la OC (cabecera) en todas las lineas.
        self.assertEqual(
            invoice["vendorInvoiceLine"][0]["fechaRequerida"],
            "2026-09-01T00:00:00",
        )
        self.assertEqual(
            invoice["vendorInvoiceLine"][0]["fechaPrometida"],
            "2026-10-15T00:00:00",
        )

        # Consolidacion por producto: item 1 (85) y item 2 (40).
        lines = {l["noProducto"]: l for l in invoice["vendorInvoiceLine"]}
        self.assertEqual(set(lines.keys()), {"ITEM-GP-1", "ITEM-GP-2"})
        self.assertEqual(lines["ITEM-GP-1"]["cantidad"], 85)
        self.assertAlmostEqual(lines["ITEM-GP-1"]["precio"], 31.58)
        self.assertEqual(lines["ITEM-GP-1"]["noLineaRecepcion"], 1)
        self.assertEqual(lines["ITEM-GP-1"]["unidadMedida"], "UN")
        self.assertEqual(lines["ITEM-GP-1"]["noRecepcion"], "GP-PO-0001")
        self.assertEqual(lines["ITEM-GP-1"]["noPedido"], "")
        self.assertEqual(lines["ITEM-GP-2"]["noLineaRecepcion"], 2)

        # El producto de la OC que la factura no trae (ITEM-GP-3) se omite.
        self.assertNotIn("ITEM-GP-3", lines)

        # Persistencia GP + confirmacion sim: BCC -> A.
        row = self.store.get("qp_SP_DocumentDetail", name)
        self.assertEqual(row["nvfac_esta"], "A")
        inv = self.store.query("qp_SP_PurchaseInvoice")
        self.assertEqual(len(inv), 1)
        self.assertEqual(inv[0]["qp_sync_flow"], "GP")
        self.assertEqual(inv[0]["invoice_id"], "SIMGPFAC-GP-0001")
        self.assertEqual(inv[0]["gp_tipo_factura_doc"], 2)

    def test_tipo2_consolida_duplicados_de_mismo_producto(self):
        name = _seed_doc(self.store)
        # Dos lineas en la factura del mismo producto -> una sola linea GP.
        _seed_detail_line(self.store, name, "SUP-1", 50, 10.0)
        _seed_detail_line(self.store, name, "SUP-1", 30, 10.0)

        calls = {"payload": None}

        def send_request_fn(endpoint_code, payload):
            calls["payload"] = payload
            return {"Result": 0, "invoices": [
                {"doc_number": "SIMGP2", "error": ""}
            ]}, 200

        result = self._run([name], send_request_fn=send_request_fn)

        self.assertEqual(len(result["approved"]), 1)
        lines = calls["payload"][0]["vendorInvoiceLine"]
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["noProducto"], "ITEM-GP-1")
        self.assertEqual(lines[0]["cantidad"], 80)
        self.assertAlmostEqual(lines[0]["precio"], 10.0)
        self.assertEqual(lines[0]["noLineaRecepcion"], 1)

    def test_proveedor_servicio_envia_tipo3(self):
        name = _seed_doc(
            self.store,
            nit=seeds.GP_SIM_SERVICE_NIT,
            nume="FAC-GP-SRV-0001",
            nvfac_orde="GP-PO-SRV",
        )
        _seed_detail_line(self.store, name, "SRV-1", 2, 100.0)

        calls = {"payload": None}

        def send_request_fn(endpoint_code, payload):
            calls["payload"] = payload
            return {"Result": 0, "invoices": [
                {"doc_number": "SIMGP3", "error": ""}
            ]}, 200

        result = self._run([name], send_request_fn=send_request_fn)

        self.assertEqual(len(result["approved"]), 1)
        invoice = calls["payload"][0]
        self.assertEqual(invoice["tipoFacturaDoc"], 3)
        # Proveedor de servicio: la peticion va SOLO con la cabecera, sin
        # productos (vendorInvoiceLine vacio) y sin validar homologaciones.
        self.assertEqual(invoice["vendorInvoiceLine"], [])
        self.assertEqual(
            result["errors"], []
        )
        inv = self.store.query("qp_SP_PurchaseInvoice")
        self.assertEqual(len(inv), 1)
        self.assertEqual(inv[0]["gp_tipo_factura_doc"], 3)

    def test_proveedor_servicio_sin_homologacion_envia_vacio(self):
        # Un producto sin homologacion en un proveedor de servicio NO se
        # valida: la factura tipo 3 sigue enviandose sin lineas.
        name = _seed_doc(
            self.store,
            nit=seeds.GP_SIM_SERVICE_NIT,
            nume="FAC-GP-SRV-MISSING",
            nvfac_orde="GP-PO-SRV",
        )
        _seed_detail_line(self.store, name, "SRV-99", 1, 5.0)

        calls = {"payload": None}

        def send_request_fn(endpoint_code, payload):
            calls["payload"] = payload
            return {"Result": 0, "invoices": [
                {"doc_number": "SIMGP3", "error": ""}
            ]}, 200

        result = self._run([name], send_request_fn=send_request_fn)

        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(result["errors"], [])
        invoice = calls["payload"][0]
        self.assertEqual(invoice["tipoFacturaDoc"], 3)
        self.assertEqual(invoice["vendorInvoiceLine"], [])

    def test_codigo_sin_homologacion_no_envia(self):
        name = _seed_doc(self.store, nume="FAC-GP-MISSING")
        _seed_detail_line(self.store, name, "SUP-9", 1, 5.0)

        calls = {"sent": 0}

        def send_request_fn(endpoint_code, payload):
            calls["sent"] += 1
            return {"Result": 0, "invoices": []}, 200

        result = self._run([name], send_request_fn=send_request_fn)

        self.assertEqual(result["approved"], [])
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("Faltan homologaciones", result["errors"][0]["error"])
        self.assertEqual(calls["sent"], 0)

    def test_nota_credito_referencia_cxp_envia_tipo4_sin_productos(self):
        # NC (nvtip_docu == "C") que referencia una factura de compra tipo 3
        # (CxP): tipofacturadoc = 4 y SIN productos. La referencia se extrae
        # del XML adjunto y se resuelve por name en qp_SP_PurchaseInvoice.
        name = _seed_nc_doc(self.store, "SETT0501293", pi_gp_tipo=3)

        calls = {"payload": None}

        def send_request_fn(endpoint_code, payload):
            calls["payload"] = payload
            return {"Result": 0, "invoices": [
                {"doc_number": "SIMGP4", "error": ""}
            ]}, 200

        result = self._run([name], send_request_fn=send_request_fn)

        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(result["errors"], [])
        invoice = calls["payload"][0]
        self.assertEqual(invoice["tipoFacturaDoc"], 4)
        # NC tipo 4 siempre se envia SIN productos.
        self.assertEqual(invoice["vendorInvoiceLine"], [])
        inv = self.store.query(
            "qp_SP_PurchaseInvoice",
            filters={"nvfac_nume": ["not in", ["SETT0501293"]]},
        )
        self.assertEqual(len(inv), 1)
        self.assertEqual(inv[0]["gp_tipo_factura_doc"], 4)

    def test_nota_credito_referencia_factura_envia_tipo5_con_productos(self):
        # NC que referencia una factura de compra tipo 2 (OC sin recepciones):
        # tipofacturadoc = 5. La linea se envia como tipo 1: noRecepcion usa el
        # confirmation_id de la qp_SP_PurchaseInvoiceBC de la referencia y
        # noPedido lleva la orden (order_no de la OC de la referencia).
        name = _seed_nc_doc(self.store, "SETT0501294", pi_gp_tipo=2,
                            purchase_order="PO-REF-0002", bank_qty=5,
                            confirmation_id="REC-CONF-0002")
        _seed_detail_line(self.store, name, "SUP-1", 2, 10.0)

        calls = {"payload": None}

        def send_request_fn(endpoint_code, payload):
            calls["payload"] = payload
            return {"Result": 0, "invoices": [
                {"doc_number": "SIMGP5", "error": ""}
            ]}, 200

        result = self._run([name], send_request_fn=send_request_fn)

        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(result["errors"], [])
        invoice = calls["payload"][0]
        self.assertEqual(invoice["tipoFacturaDoc"], 5)
        self.assertEqual(len(invoice["vendorInvoiceLine"]), 1)
        line = invoice["vendorInvoiceLine"][0]
        self.assertEqual(line["noProducto"], "ITEM-GP-1")
        self.assertEqual(line["cantidad"], 2)
        # Referencia tipo 2 enviada como tipo 1: noRecepcion = confirmation_id
        # de la PIBC de la referencia, noPedido = orden.
        self.assertEqual(line["noRecepcion"], "REC-CONF-0002")
        self.assertEqual(line["noPedido"], "PO-REF-0002")
        # noLineaRecepcion = idx de la linea de la OC de la referencia.
        self.assertEqual(line["noLineaRecepcion"], 3)
        inv = self.store.query(
            "qp_SP_PurchaseInvoice",
            filters={"nvfac_nume": ["not in", ["SETT0501294"]]},
        )
        self.assertEqual(len(inv), 1)
        self.assertEqual(inv[0]["gp_tipo_factura_doc"], 5)
        # Se persistio el consumo del banco por linea.
        consumption = self.store.query("qp_SP_Devolution")
        self.assertEqual(len(consumption), 1)
        self.assertEqual(consumption[0]["item_code"], "ITEM-GP-1")
        self.assertEqual(consumption[0]["qty"], 2)
        self.assertEqual(consumption[0]["order_no"], "PO-REF-0002")
        self.assertEqual(consumption[0]["receiving_no"], "")

    def test_nota_credito_tipo5_referencia_tipo1_usa_recibo(self):
        # Referencia tipo 1 (con recepcion): la linea de la NC lleva el recibo
        # y la orden de la linea de la referencia.
        name = _seed_nc_doc(self.store, "SETT0501295", pi_gp_tipo=1,
                            purchase_order="PO-REF-0001", bank_qty=5)
        _seed_detail_line(self.store, name, "SUP-1", 3, 10.0)

        calls = {"payload": None}

        def send_request_fn(endpoint_code, payload):
            calls["payload"] = payload
            return {"Result": 0, "invoices": [
                {"doc_number": "SIMGP5B", "error": ""}
            ]}, 200

        result = self._run([name], send_request_fn=send_request_fn)

        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(result["errors"], [])
        invoice = calls["payload"][0]
        self.assertEqual(invoice["tipoFacturaDoc"], 5)
        line = invoice["vendorInvoiceLine"][0]
        self.assertEqual(line["noProducto"], "ITEM-GP-1")
        # Referencia tipo 1: noRecepcion = recibo, noPedido = orden.
        self.assertEqual(line["noRecepcion"], "REC-SETT0501295")
        self.assertEqual(line["noPedido"], "PO-REF-0001")
        # noLineaRecepcion = idx de la linea de la recepcion de la referencia.
        self.assertEqual(line["noLineaRecepcion"], 5)
        consumption = self.store.query("qp_SP_Devolution")
        self.assertEqual(len(consumption), 1)
        self.assertEqual(consumption[0]["receiving_no"], "REC-SETT0501295")
        self.assertEqual(consumption[0]["order_no"], "PO-REF-0001")

    def test_nota_credito_tipo5_excede_banco_no_envia(self):
        # La devolucion excede el banco de la referencia: la NC no se envia
        # (queda en error) y no hay consumo persistido.
        name = _seed_nc_doc(self.store, "SETT0501296", pi_gp_tipo=2,
                            purchase_order="PO-REF-0003", bank_qty=1,
                            confirmation_id="REC-CONF-0003")
        _seed_detail_line(self.store, name, "SUP-1", 2, 10.0)

        calls = {"sent": 0}

        def send_request_fn(endpoint_code, payload):
            calls["sent"] += 1
            return {"Result": 0, "invoices": []}, 200

        result = self._run([name], send_request_fn=send_request_fn)

        self.assertEqual(result["approved"], [])
        self.assertEqual(calls["sent"], 0)
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("excede", result["errors"][0]["error"].lower())
        self.assertEqual(self.store.query("qp_SP_Devolution"), [])

    def test_nota_credito_tipo5_exceso_force_envia(self):
        # Con force=True (aprobacion manual confirmada) el exceso se omite y
        # la NC se envia igual.
        name = _seed_nc_doc(self.store, "SETT0501297", pi_gp_tipo=2,
                            purchase_order="PO-REF-0004", bank_qty=1,
                            confirmation_id="REC-CONF-0004")
        _seed_detail_line(self.store, name, "SUP-1", 2, 10.0)

        calls = {"payload": None}

        def send_request_fn(endpoint_code, payload):
            calls["payload"] = payload
            return {"Result": 0, "invoices": [
                {"doc_number": "SIMGP5C", "error": ""}
            ]}, 200

        with patch.object(_approve_base.runtime, "is_simulation_enabled",
                          return_value=True), \
             patch.object(_approve_base, "frappe", MagicMock()), \
             patch("qp_supplier_front.simulation.session.store",
                   return_value=self.store):
            result = _approve_base.approve_documents_core(
                [name], backend="GP", force=True,
                send_request_fn=send_request_fn,
            )

        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(result["errors"], [])
        invoice = calls["payload"][0]
        self.assertEqual(invoice["tipoFacturaDoc"], 5)
        self.assertEqual(len(invoice["vendorInvoiceLine"]), 1)

    def test_nota_credito_tipo5_referencia_no_confirmada_bloquea(self):
        # Referencia tipo 2 sin confirmation_id: la NC no se envia (aun con
        # force) y muestra la alerta de referencia no confirmada.
        name = _seed_nc_doc(self.store, "SETT0501300", pi_gp_tipo=2,
                            purchase_order="PO-REF-0007", bank_qty=5)
        _seed_detail_line(self.store, name, "SUP-1", 2, 10.0)

        calls = {"sent": 0}

        def send_request_fn(endpoint_code, payload):
            calls["sent"] += 1
            return {"Result": 0, "invoices": []}, 200

        with patch.object(_approve_base.runtime, "is_simulation_enabled",
                          return_value=True), \
             patch.object(_approve_base, "frappe", MagicMock()), \
             patch("qp_supplier_front.simulation.session.store",
                   return_value=self.store):
            result = _approve_base.approve_documents_core(
                [name], backend="GP", force=True,
                send_request_fn=send_request_fn,
            )

        self.assertEqual(result["approved"], [])
        self.assertEqual(calls["sent"], 0)
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("confirmada", result["errors"][0]["error"].lower())
        self.assertEqual(self.store.query("qp_SP_Devolution"), [])

    def test_nota_credito_sin_referencia_resoluble_falla(self):
        # Sin referencia en el XML (o sin factura de compra) la NC NO se
        # envia: queda en error y no pasa a BCC/A.
        name = _seed_doc(
            self.store,
            nume="NC-GP-NOREF",
            nvfac_conv="2",
            nvfac_orde="",
            nvtip_docu="C",
        )

        calls = {"sent": 0}

        def send_request_fn(endpoint_code, payload):
            calls["sent"] += 1
            return {"Result": 0, "invoices": []}, 200

        result = self._run([name], send_request_fn=send_request_fn)

        self.assertEqual(result["approved"], [])
        self.assertEqual(calls["sent"], 0)
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("referencia", result["errors"][0]["error"].lower())

    def test_nota_credito_tipo5_prevalidacion_reporta_exceso(self):
        # La pre-validacion (collect_document_violations) reporta el exceso
        # del banco de la NC tipo 5 para que el front muestre la confirmacion
        # antes de aprobar manualmente (force).
        name = _seed_nc_doc(self.store, "SETT0501298", pi_gp_tipo=2,
                            purchase_order="PO-REF-0005", bank_qty=1,
                            confirmation_id="REC-CONF-0005")
        _seed_detail_line(self.store, name, "SUP-1", 2, 10.0)

        with patch.object(_approve_base.runtime, "is_simulation_enabled",
                          return_value=True), \
             patch.object(_approve_base, "frappe", MagicMock()), \
             patch("qp_supplier_front.simulation.session.store",
                   return_value=self.store):
            violations = _approve_base.collect_document_violations(
                [name], backend="GP"
            )

        self.assertEqual(len(violations), 1)
        self.assertIn("excede", violations[0]["violations"][0].lower())

    def test_nota_credito_tipo5_sin_exceso_no_reporta_violacion(self):
        name = _seed_nc_doc(self.store, "SETT0501299", pi_gp_tipo=2,
                            purchase_order="PO-REF-0006", bank_qty=5,
                            confirmation_id="REC-CONF-0006")
        _seed_detail_line(self.store, name, "SUP-1", 2, 10.0)

        with patch.object(_approve_base.runtime, "is_simulation_enabled",
                          return_value=True), \
             patch.object(_approve_base, "frappe", MagicMock()), \
             patch("qp_supplier_front.simulation.session.store",
                   return_value=self.store):
            violations = _approve_base.collect_document_violations(
                [name], backend="GP"
            )

        self.assertEqual(violations, [])

    def test_nota_credito_tipo5_sin_confirmacion_no_es_violacion_forceable(self):
        # La falta de confirmation_id de la referencia NO se reporta como
        # violacion: el front no ofrece aprobar manualmente (no es forceable).
        name = _seed_nc_doc(self.store, "SETT0501301", pi_gp_tipo=2,
                            purchase_order="PO-REF-0008", bank_qty=5)
        _seed_detail_line(self.store, name, "SUP-1", 2, 10.0)

        with patch.object(_approve_base.runtime, "is_simulation_enabled",
                          return_value=True), \
             patch.object(_approve_base, "frappe", MagicMock()), \
             patch("qp_supplier_front.simulation.session.store",
                   return_value=self.store):
            violations = _approve_base.collect_document_violations(
                [name], backend="GP"
            )

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()