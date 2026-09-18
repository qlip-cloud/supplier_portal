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
              total=3000.0):
    name = name or "{}:{}".format(nit, nume)
    store.insert("qp_SP_DocumentDetail", {
        "name": name,
        "nvfac_nume": nume,
        "nvpro_ndoc": nit,
        "nvfac_fech": "2026-09-15 10:00:00",
        "nvfac_cufe": "CUFE-GP",
        "nvtip_docu": "FAC",
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
        # Homologa siempre y aplica la regla de OC (idx de la OC).
        lines = invoice["vendorInvoiceLine"]
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["noProducto"], "ITEM-SRV-2")
        self.assertEqual(lines[0]["noLineaRecepcion"], 2)
        self.assertEqual(lines[0]["noRecepcion"], "GP-PO-SRV")
        self.assertEqual(lines[0]["noPedido"], "")

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


if __name__ == "__main__":
    unittest.main()