"""Controller override de Purchase Receipt.

Registra en archivo (``services/inbound_api_log.py``) los requests de API
que fallan durante el insert (por ejemplo ``LinkValidationError`` en
``_validate_links``, que ocurre antes de ``after_insert``). El flujo exitoso
sigue usando el doc_event ``after_insert`` definido en hooks.py.
"""

from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt

from qp_supplier_front.services.inbound_api_log import log_failed_api_request


class QpPurchaseReceipt(PurchaseReceipt):

    def insert(self, *args, **kwargs):
        try:
            return super(QpPurchaseReceipt, self).insert(*args, **kwargs)
        except Exception as error:
            log_failed_api_request(self, error)
            raise
