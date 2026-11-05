# -*- coding: utf-8 -*-
"""
test_sync_by_supplier.py
========================
Pruebas unitarias para uses_cases/documents/sync_by_supplier.py
Cubre todos los puntos de falla del flujo de orquestacion.

Completamente aisladas de Frappe y de la base de datos.
Ejecutar con: python -m pytest qp_supplier_front/tests/test_sync_by_supplier.py -v
"""
import unittest
from qp_supplier_front.uses_cases.documents.sync_by_supplier import (
    sync_by_supplier,
    get_default_nvfac_esta,
    get_yesterday_date_str,
)


# ---------------------------------------------------------------------------
# Escenarios de exito
# ---------------------------------------------------------------------------
class TestSyncBySupplierHappyPath(unittest.TestCase):

    def setUp(self):
        self.supplier_id = "PROV-001"
        self.tax_id = "123456789"
        self.sentinel_log = "SYNC-LOG-00001"
        self.ldocuments = [
            {"Nvfac_cont": "1", "Nvfac_nume": "FAC-001"},
            {"Nvfac_cont": "2", "Nvfac_nume": "FAC-002"},
        ]
        self.success_response = {"Result": 0, "LDocuments": self.ldocuments}

    def test_happy_path_with_documents(self):
        """Flujo completo exitoso: log + lineas creadas, commit ejecutado."""
        lines_called = []
        commit_called = []
        log_name = sync_by_supplier(
            supplier_id=self.supplier_id,
            get_tax_id_fn=lambda s: self.tax_id,
            send_request_fn=lambda **kw: (self.success_response, 200),
            create_log_fn=lambda *a, **kw: self.sentinel_log,
            create_lines_fn=lambda lg, docs: lines_called.append(True),
            commit_fn=lambda: commit_called.append(True),
        )
        self.assertEqual(log_name, self.sentinel_log)
        self.assertTrue(lines_called)
        self.assertTrue(commit_called)

    def test_happy_path_no_documents(self):
        """LDocuments vacio: commit se ejecuta, lines tambien se llama con lista vacia."""
        lines_called = []
        commit_called = []
        sync_by_supplier(
            supplier_id=self.supplier_id,
            get_tax_id_fn=lambda s: self.tax_id,
            send_request_fn=lambda **kw: ({"Result": 0, "LDocuments": []}, 200),
            create_log_fn=lambda *a, **kw: self.sentinel_log,
            create_lines_fn=lambda lg, docs: lines_called.append(True),
            commit_fn=lambda: commit_called.append(True),
        )
        self.assertTrue(lines_called)
        self.assertTrue(commit_called)

    def test_ldocuments_key_missing(self):
        """Si la respuesta no trae LDocuments, lines recibe lista vacia."""
        lines_docs = []
        sync_by_supplier(
            supplier_id=self.supplier_id,
            get_tax_id_fn=lambda s: self.tax_id,
            send_request_fn=lambda **kw: ({"Result": 0}, 200),
            create_log_fn=lambda *a, **kw: self.sentinel_log,
            create_lines_fn=lambda lg, docs: lines_docs.append(docs),
            commit_fn=lambda: None,
        )
        self.assertEqual(lines_docs[0], [])

    def test_ldocuments_is_none(self):
        """Si LDocuments es None explicitamente, create_lines recibe None."""
        lines_docs = []
        sync_by_supplier(
            supplier_id=self.supplier_id,
            get_tax_id_fn=lambda s: self.tax_id,
            send_request_fn=lambda **kw: ({"Result": 0, "LDocuments": None}, 200),
            create_log_fn=lambda *a, **kw: self.sentinel_log,
            create_lines_fn=lambda lg, docs: lines_docs.append(docs),
            commit_fn=lambda: None,
        )
        self.assertIsNone(lines_docs[0])

    def test_creates_log_regardless_of_documents(self):
        """create_log se llama incluso si no hay documentos que sincronizar."""
        log_called = []
        sync_by_supplier(
            supplier_id=self.supplier_id,
            get_tax_id_fn=lambda s: self.tax_id,
            send_request_fn=lambda **kw: ({"Result": 0, "LDocuments": []}, 200),
            create_log_fn=lambda *a, **kw: log_called.append(True) or self.sentinel_log,
            create_lines_fn=lambda *a, **kw: None,
            commit_fn=lambda: None,
        )
        self.assertTrue(log_called)


# ---------------------------------------------------------------------------
# Fallos en cada punto de inyeccion
# ---------------------------------------------------------------------------
class TestSyncBySupplierGetTaxIdFnFailures(unittest.TestCase):

    def test_does_not_exist_error_propagates(self):
        """Si el proveedor no existe, la excepcion se propaga."""
        def raise_does_not_exist(sid):
            raise ValueError("Supplier {} not found".format(sid))

        with self.assertRaises(ValueError) as ctx:
            sync_by_supplier(
                supplier_id="INVALID",
                get_tax_id_fn=raise_does_not_exist,
                send_request_fn=lambda **kw: ({"Result": 0}, 200),
                create_log_fn=lambda *a, **kw: "LOG",
                create_lines_fn=lambda *a, **kw: None,
                commit_fn=lambda: None,
            )
        self.assertIn("not found", str(ctx.exception))

    def test_commit_not_called_when_get_tax_id_fails(self):
        """Si get_tax_id falla, commit NO se ejecuta."""
        commit_called = []
        with self.assertRaises(RuntimeError):
            sync_by_supplier(
                supplier_id="INVALID",
                get_tax_id_fn=lambda s: (_ for _ in ()).throw(RuntimeError("DB error")),
                send_request_fn=lambda **kw: ({"Result": 0}, 200),
                create_log_fn=lambda *a, **kw: "LOG",
                create_lines_fn=lambda *a, **kw: None,
                commit_fn=lambda: commit_called.append(True),
            )
        self.assertFalse(commit_called)


class TestSyncBySupplierSendRequestFnFailures(unittest.TestCase):

    def setUp(self):
        self.supplier_id = "PROV-001"
        self.tax_id = "123456789"
        self.committed = []

    def _base_kwargs(self, send_request_fn):
        return dict(
            supplier_id=self.supplier_id,
            get_tax_id_fn=lambda s: self.tax_id,
            send_request_fn=send_request_fn,
            create_log_fn=lambda *a, **kw: "LOG",
            create_lines_fn=lambda *a, **kw: None,
            commit_fn=lambda: self.committed.append(True),
        )

    def test_connection_error_propagates(self):
        """Error de red -> propaga, no hace commit."""
        def fail(**kw):
            raise ConnectionError("Connection refused")

        with self.assertRaises(ConnectionError):
            sync_by_supplier(**self._base_kwargs(fail))
        self.assertFalse(self.committed)

    def test_timeout_error_propagates(self):
        """Timeout -> propaga, no hace commit."""
        def fail(**kw):
            raise TimeoutError("Request timed out")

        with self.assertRaises(TimeoutError):
            sync_by_supplier(**self._base_kwargs(fail))
        self.assertFalse(self.committed)

    def test_generic_error_propagates(self):
        """Error generico en la API -> propaga tal cual."""
        def fail(**kw):
            raise RuntimeError("Unexpected API error")

        with self.assertRaises(RuntimeError):
            sync_by_supplier(**self._base_kwargs(fail))
        self.assertFalse(self.committed)

    def test_creates_log_even_when_response_is_error(self):
        """El log se crea incluso si la API retorna error (Result != 0)."""
        log_called = []
        sync_by_supplier(
            supplier_id=self.supplier_id,
            get_tax_id_fn=lambda s: self.tax_id,
            send_request_fn=lambda **kw: ({"Result": 1, "Description": "No data"}, 200),
            create_log_fn=lambda *a, **kw: log_called.append(True) or "LOG",
            create_lines_fn=lambda *a, **kw: None,
            commit_fn=lambda: self.committed.append(True),
        )
        self.assertTrue(log_called)
        self.assertTrue(self.committed)

    def test_creates_log_even_when_http_status_is_error(self):
        """El log se crea incluso si el HTTP status es 500."""
        log_called = []
        sync_by_supplier(
            supplier_id=self.supplier_id,
            get_tax_id_fn=lambda s: self.tax_id,
            send_request_fn=lambda **kw: ({"Result": 0}, 500),
            create_log_fn=lambda *a, **kw: log_called.append(True) or "LOG",
            create_lines_fn=lambda *a, **kw: None,
            commit_fn=lambda: self.committed.append(True),
        )
        self.assertTrue(log_called)
        self.assertTrue(self.committed)


class TestSyncBySupplierCreateLogFnFailures(unittest.TestCase):

    def test_create_log_failure_propagates_and_no_commit(self):
        """Si create_log falla (DB insert error), no se hace commit."""
        committed = []
        def fail(*a, **kw):
            raise OSError("Disk full")

        with self.assertRaises(OSError):
            sync_by_supplier(
                supplier_id="PROV-001",
                get_tax_id_fn=lambda s: "123",
                send_request_fn=lambda **kw: ({"Result": 0, "LDocuments": []}, 200),
                create_log_fn=fail,
                create_lines_fn=lambda *a, **kw: None,
                commit_fn=lambda: committed.append(True),
            )
        self.assertFalse(committed)


class TestSyncBySupplierCreateLinesFnFailures(unittest.TestCase):

    def test_create_lines_failure_propagates_and_no_commit(self):
        """Si create_lines falla (DB error en linea), commit no se ejecuta."""
        committed = []
        def fail(*a, **kw):
            raise RuntimeError("Line insert failed")

        with self.assertRaises(RuntimeError):
            sync_by_supplier(
                supplier_id="PROV-001",
                get_tax_id_fn=lambda s: "123",
                send_request_fn=lambda **kw: ({"Result": 0, "LDocuments": [{"Nvfac_cont": "1"}]}, 200),
                create_log_fn=lambda *a, **kw: "LOG",
                create_lines_fn=fail,
                commit_fn=lambda: committed.append(True),
            )
        self.assertFalse(committed)


class TestSyncBySupplierCommitFnFailures(unittest.TestCase):

    def test_commit_failure_propagates(self):
        """Si commit falla, la excepcion se propaga al caller."""
        def fail():
            raise RuntimeError("Commit failed")

        with self.assertRaises(RuntimeError):
            sync_by_supplier(
                supplier_id="PROV-001",
                get_tax_id_fn=lambda s: "123",
                send_request_fn=lambda **kw: ({"Result": 0, "LDocuments": []}, 200),
                create_log_fn=lambda *a, **kw: "LOG",
                create_lines_fn=lambda *a, **kw: None,
                commit_fn=fail,
            )


# ---------------------------------------------------------------------------
# Ramas logicas
# ---------------------------------------------------------------------------
class TestSyncBySupplierLogicBranches(unittest.TestCase):

    def test_api_result_non_zero_skips_lines(self):
        """Result != 0 -> NO se llama a create_lines_fn."""
        lines_called = []
        sync_by_supplier(
            supplier_id="PROV-001",
            get_tax_id_fn=lambda s: "123",
            send_request_fn=lambda **kw: ({"Result": 1}, 200),
            create_log_fn=lambda *a, **kw: "LOG",
            create_lines_fn=lambda *a, **kw: lines_called.append(True),
            commit_fn=lambda: None,
        )
        self.assertFalse(lines_called)

    def test_http_status_not_200_skips_lines(self):
        """status != 200 -> NO se llama a create_lines_fn."""
        lines_called = []
        sync_by_supplier(
            supplier_id="PROV-001",
            get_tax_id_fn=lambda s: "123",
            send_request_fn=lambda **kw: ({"Result": 0}, 500),
            create_log_fn=lambda *a, **kw: "LOG",
            create_lines_fn=lambda *a, **kw: lines_called.append(True),
            commit_fn=lambda: None,
        )
        self.assertFalse(lines_called)

    def test_commit_is_always_called_after_successful_flow(self):
        """commit se llama incluso si no hay lineas que crear."""
        committed = []
        sync_by_supplier(
            supplier_id="PROV-001",
            get_tax_id_fn=lambda s: "123",
            send_request_fn=lambda **kw: ({"Result": 0, "LDocuments": []}, 200),
            create_log_fn=lambda *a, **kw: "LOG",
            create_lines_fn=lambda *a, **kw: None,
            commit_fn=lambda: committed.append(True),
        )
        self.assertTrue(committed)

    def test_send_request_receives_correct_parameters(self):
        """send_request recibe endpoint, param y is_query_param correctos."""
        captured = {}
        def spy(endpoint_code, param, is_query_param):
            captured["endpoint"] = endpoint_code
            captured["param"] = param
            captured["is_query"] = is_query_param
            return ({"Result": 0}, 200)

        sync_by_supplier(
            supplier_id="PROV-001",
            get_tax_id_fn=lambda s: "123",
            send_request_fn=spy,
            create_log_fn=lambda *a, **kw: "LOG",
            create_lines_fn=lambda *a, **kw: None,
            commit_fn=lambda: None,
        )
        self.assertEqual(captured["endpoint"], "documenteme_list_documents")
        self.assertIn("nvemp_nnit=123", captured["param"])
        self.assertTrue(captured["is_query"])

    def test_create_log_receives_all_data(self):
        """create_log recibe todos los parametros en el orden correcto."""
        captured = {}
        def spy(supplier_id, tax_id, endpoint_code, payload, response, status):
            captured.update(
                supplier_id=supplier_id,
                tax_id=tax_id,
                endpoint=endpoint_code,
                payload=payload,
                response=response,
                status=status,
            )
            return "LOG"

        sync_by_supplier(
            supplier_id="PROV-001",
            get_tax_id_fn=lambda s: "123",
            send_request_fn=lambda **kw: ({"Result": 0}, 200),
            create_log_fn=spy,
            create_lines_fn=lambda *a, **kw: None,
            commit_fn=lambda: None,
        )
        self.assertEqual(captured["supplier_id"], "PROV-001")
        self.assertEqual(captured["tax_id"], "123")
        self.assertEqual(captured["endpoint"], "documenteme_list_documents")
        self.assertTrue(captured["payload"])
        self.assertEqual(captured["response"], {"Result": 0})
        self.assertEqual(captured["status"], 200)

    def test_create_lines_receives_log_name_and_documents(self):
        """create_lines recibe el log_name y la lista de documentos."""
        captured = {}
        def spy(log_name, documents):
            captured["log_name"] = log_name
            captured["documents"] = documents

        docs = [{"Nvfac_cont": "1"}]
        sync_by_supplier(
            supplier_id="PROV-001",
            get_tax_id_fn=lambda s: "123",
            send_request_fn=lambda **kw: ({"Result": 0, "LDocuments": docs}, 200),
            create_log_fn=lambda *a, **kw: "LOG-001",
            create_lines_fn=spy,
            commit_fn=lambda: None,
        )
        self.assertEqual(captured["log_name"], "LOG-001")
        self.assertEqual(captured["documents"], docs)


# ---------------------------------------------------------------------------
# Parametros por defecto
# ---------------------------------------------------------------------------
class TestSyncBySupplierDefaultParameters(unittest.TestCase):

    def test_default_nvfac_values_when_none(self):
        """Si no se pasan nvfac_*, se usan los valores por defecto."""
        captured = {}
        def spy(**kw):
            captured["param"] = kw["param"]
            return ({"Result": 0}, 200)

        sync_by_supplier(
            supplier_id="PROV-001",
            get_tax_id_fn=lambda s: "123",
            send_request_fn=spy,
            create_log_fn=lambda *a, **kw: "LOG",
            create_lines_fn=lambda *a, **kw: None,
            commit_fn=lambda: None,
        )
        param = captured["param"]
        self.assertIn("nvfac_esta=" + get_default_nvfac_esta(), param)

    def test_custom_nvfac_values_override_defaults(self):
        """Los parametros explicitos reemplazan a los valores por defecto."""
        captured = {}
        def spy(**kw):
            captured["param"] = kw["param"]
            return ({"Result": 0}, 200)

        sync_by_supplier(
            supplier_id="PROV-001",
            get_tax_id_fn=lambda s: "123",
            send_request_fn=spy,
            create_log_fn=lambda *a, **kw: "LOG",
            create_lines_fn=lambda *a, **kw: None,
            commit_fn=lambda: None,
            nvfac_esta="A",
            nvfac_fini="01/01/2025",
            nvfac_ffin="31/12/2025",
        )
        param = captured["param"]
        self.assertIn("nvfac_esta=A", param)
        self.assertIn("nvfac_fini=01/01/2025", param)
        self.assertIn("nvfac_ffin=31/12/2025", param)


# ---------------------------------------------------------------------------
# Escenarios limites / robustez
# ---------------------------------------------------------------------------
class TestSyncBySupplierEdgeCases(unittest.TestCase):

    def test_tax_id_returns_none(self):
        """Si get_tax_id retorna None, aun asi se construye el param."""
        called = []
        sync_by_supplier(
            supplier_id="PROV-001",
            get_tax_id_fn=lambda s: None,
            send_request_fn=lambda **kw: called.append(True) or ({"Result": 0}, 200),
            create_log_fn=lambda *a, **kw: "LOG",
            create_lines_fn=lambda *a, **kw: None,
            commit_fn=lambda: None,
        )
        self.assertTrue(called)

    def test_response_is_none(self):
        """send_request retorna (None, 200): is_successful_response no crashea,
        log se crea, lines NO se crean, commit se ejecuta."""
        sent = []
        log_response = []
        lines_called = []
        commit_called = []
        def spy(*a, **kw):
            sent.append(True)
            return (None, 200)

        sync_by_supplier(
            supplier_id="PROV-001",
            get_tax_id_fn=lambda s: "123",
            send_request_fn=spy,
            create_log_fn=lambda *a, **kw: log_response.append(a[4]) or "LOG",
            create_lines_fn=lambda *a, **kw: lines_called.append(True),
            commit_fn=lambda: commit_called.append(True),
        )
        self.assertTrue(sent)
        self.assertIsNone(log_response[0])
        self.assertFalse(lines_called)
        self.assertTrue(commit_called)

    def test_null_response_and_null_status(self):
        """send_request retorna (None, None): is_successful_response no crashea,
        log recibe ambos None, lines no se crean, commit se ejecuta."""
        log_response = []
        log_status = []
        lines_called = []
        commit_called = []
        def spy(*a, **kw):
            return (None, None)

        sync_by_supplier(
            supplier_id="PROV-001",
            get_tax_id_fn=lambda s: "123",
            send_request_fn=spy,
            create_log_fn=lambda *a, **kw: (
                log_response.append(a[4]) or log_status.append(a[5]) or "LOG"
            ),
            create_lines_fn=lambda *a, **kw: lines_called.append(True),
            commit_fn=lambda: commit_called.append(True),
        )
        self.assertIsNone(log_response[0])
        self.assertIsNone(log_status[0])
        self.assertFalse(lines_called)
        self.assertTrue(commit_called)

    def test_response_without_result_key(self):
        """Si response no tiene 'Result', is_successful_response retorna False -> no lines."""
        lines_called = []
        commit_called = []
        sync_by_supplier(
            supplier_id="PROV-001",
            get_tax_id_fn=lambda s: "123",
            send_request_fn=lambda **kw: ({"status": "ok"}, 200),
            create_log_fn=lambda *a, **kw: "LOG",
            create_lines_fn=lambda *a, **kw: lines_called.append(True),
            commit_fn=lambda: commit_called.append(True),
        )
        self.assertFalse(lines_called)
        self.assertTrue(commit_called)


    def test_no_shared_state_between_calls(self):
        """Dos llamadas consecutivas con distintos parametros no contaminan estado."""
        call_1_tax_id = "TAX-111"
        call_2_tax_id = "TAX-222"
        captured = {"call_1_param": None, "call_2_param": None}

        def spy_for_call_1(endpoint_code, param, is_query_param):
            captured["call_1_param"] = param
            return ({"Result": 0}, 200)

        def spy_for_call_2(endpoint_code, param, is_query_param):
            captured["call_2_param"] = param
            return ({"Result": 0}, 200)

        sync_by_supplier(
            supplier_id="SUP-1",
            get_tax_id_fn=lambda s: call_1_tax_id,
            send_request_fn=spy_for_call_1,
            create_log_fn=lambda *a, **kw: "LOG-1",
            create_lines_fn=lambda *a, **kw: None,
            commit_fn=lambda: None,
        )

        sync_by_supplier(
            supplier_id="SUP-2",
            get_tax_id_fn=lambda s: call_2_tax_id,
            send_request_fn=spy_for_call_2,
            create_log_fn=lambda *a, **kw: "LOG-2",
            create_lines_fn=lambda *a, **kw: None,
            commit_fn=lambda: None,
        )

        self.assertIn(call_1_tax_id, captured["call_1_param"])
        self.assertIn(call_2_tax_id, captured["call_2_param"])


class TestDefaultFunctions(unittest.TestCase):

    def test_get_default_nvfac_esta_returns_T(self):
        self.assertEqual(get_default_nvfac_esta(), "T")

    def test_get_yesterday_date_str_format(self):
        """get_yesterday_date_str retorna fecha con formato DD/MM/YYYY."""
        date_str = get_yesterday_date_str()
        import re
        self.assertIsNotNone(re.match(r"\d{2}/\d{2}/\d{4}", date_str))


if __name__ == "__main__":
    unittest.main()
