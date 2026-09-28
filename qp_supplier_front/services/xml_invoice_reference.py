"""xml_invoice_reference.py
=========================
Extraccion de la referencia de factura (cac:InvoiceDocumentReference /
cbc:ID) desde el XML DIAN de una nota de credito.

El XML puede llegar como documento raiz (CreditNote) o envuelto en un
AttachedDocument (Documento adjunto) con el XML de la nota incrustado en el
cbc:Description del primer cac:Attachment. Ambos formatos se soportan.

La referencia (p.ej. "SETT0501293") identifica la factura de compra
(qp_SP_PurchaseInvoice) que la nota de credito ajusta.
"""

import re
import xml.etree.ElementTree as ET

CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"

DOCUMENT_ROOT_TAGS = frozenset([
    "{urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2}CreditNote",
    "{urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2}DebitNote",
    "{urn:oasis:names:specification:ubl:schema:xsd:Invoice-2}Invoice",
])

ATTACHED_DOCUMENT_TAG = (
    "{urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2}AttachedDocument"
)

INVOICE_DOCUMENT_REFERENCE_TAG = "{%s}InvoiceDocumentReference" % CAC

ID_TAG = "{%s}ID" % CBC

_EMBEDDED_XML_RE = re.compile(r"<\?xml[^>]*\?>\s*<[A-Za-z_][\w:.-]*", re.S)


def _try_parse(xml_content):
    try:
        return ET.fromstring(xml_content)
    except ET.ParseError:
        return None


def _extract_embedded_document(root):
    """XML incrustado en un AttachedDocument (primer cac:Attachment)."""
    tag_attachment = "{%s}Attachment" % CAC
    tag_ext_ref = "{%s}ExternalReference" % CAC
    tag_description = "{%s}Description" % CBC

    attachment = root.find("%s/%s/%s" % (tag_attachment, tag_ext_ref,
                                         tag_description))
    if attachment is not None and attachment.text:
        return attachment.text.strip()
    return None


def _collect_embedded_documents(xml_content):
    """Intenta parsear los documentos XML incrustados en Description.

    Algunos contenedores de adjunto llegan sin las declaraciones de
    namespace del contenedor (el arbol completo no es parseable), pero la
    nota de credito embebida si lo es. Se recorta cada bloque
    <?xml ...> <Root>...</Root> y se intenta parsear.
    """
    documents = []
    for match in _EMBEDDED_XML_RE.finditer(xml_content):
        start = match.start()
        after_decl = match.group(0).split("?>", 1)[-1].lstrip()
        root_name = after_decl[1:].split()[0]
        closer = "</{}>".format(root_name)
        end = xml_content.find(closer, start)
        if end < 0:
            continue
        fragment = xml_content[start:end + len(closer)]
        root = _try_parse(fragment)
        if root is not None:
            documents.append(root)
    return documents


def _find_invoice_document_reference_id(element):
    """Busca en cualquier punto del arbol un cac:InvoiceDocumentReference y
    devuelve el texto de su cbc:ID (la referencia de la factura ajustada)."""
    for node in element.iter():
        if node.tag != INVOICE_DOCUMENT_REFERENCE_TAG:
            continue
        id_node = node.find(ID_TAG)
        if id_node is not None and id_node.text:
            return id_node.text.strip()
        for id_node in node.iter(ID_TAG):
            if id_node.text:
                return id_node.text.strip()
    return None


def _reference_from_root(root):
    if root is None:
        return None
    if root.tag == ATTACHED_DOCUMENT_TAG:
        inner_xml = _extract_embedded_document(root)
        if inner_xml:
            inner_root = _try_parse(inner_xml)
            if inner_root is not None:
                return _find_invoice_document_reference_id(inner_root)
            return None
        return None
    if root.tag in DOCUMENT_ROOT_TAGS:
        return _find_invoice_document_reference_id(root)
    return None


def extract_invoice_document_reference(xml_content):
    """Referencia (cbc:ID) de cac:InvoiceDocumentReference en el XML DIAN.

    - Soporta un documento raiz (CreditNote/DebitNote/Invoice) o un
      AttachedDocument con la nota incrustada en el primer Attachment.
    - Si el contenedor no es parseable, intenta con cada documento XML
      embebido en Description.
    - Retorna el texto de la referencia (p.ej. "SETT0501293") o None.
    """
    if not xml_content:
        return None

    root = _try_parse(xml_content)
    reference = _reference_from_root(root)
    if reference:
        return reference

    for inner_root in _collect_embedded_documents(xml_content):
        reference = _find_invoice_document_reference_id(inner_root)
        if reference:
            return reference

    return None