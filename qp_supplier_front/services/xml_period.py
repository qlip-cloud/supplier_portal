"""xml_period.py
================
Extraccion del periodo (rango de fechas) de una nota de credito desde su XML
DIAN: <cbc:StartDate> y <cbc:EndDate>.

Cuando el proveedor no puede agregar la referencia de la factura (porque la
factura referenciada ya fue aceptada), documenteme solo permite indicar un
rango de fechas en el XML (tipicamente bajo cac:ValidityPeriod). Este parser
recupera ese rango para ofrecer al usuario el listado de facturas candidatas.

Soporta el XML como documento raiz (CreditNote/DebitNote/Invoice) o envuelto
en un AttachedDocument con el XML incrustado (mismo comportamiento tolerante
que services/xml_invoice_reference.py).
"""

import re
import xml.etree.ElementTree as ET

CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"

DOCUMENT_ROOT_TAGS = frozenset([
    "{urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2}CreditNote",
    "{urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2}DebitNote",
    "{urn:oasis:names:specification:ubl:schema:xsd:Invoice-2}Invoice",
])

ATTACHED_DOCUMENT_TAG = (
    "{urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2}AttachedDocument"
)

CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"

START_DATE_TAG = "{%s}StartDate" % CBC
END_DATE_TAG = "{%s}EndDate" % CBC

_EMBEDDED_XML_RE = re.compile(r"<\?xml[^>]*\?>\s*<[A-Za-z_][\w:.-]*", re.S)


def _try_parse(xml_content):
    try:
        return ET.fromstring(xml_content)
    except ET.ParseError:
        return None


def _collect_embedded_documents(xml_content):
    """XML incrustado en un AttachedDocument (primer cac:Attachment/cbc:Description)."""
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


def _find_period_dates(element):
    """Primer cbc:StartDate y primer cbc:EndDate encontrados en cualquier punto."""
    start = None
    end = None
    for node in element.iter():
        text = node.text.strip() if node.text else ""
        if not text:
            continue
        if node.tag == START_DATE_TAG and start is None:
            start = text
        elif node.tag == END_DATE_TAG and end is None:
            end = text
        if start is not None and end is not None:
            break
    return start, end


def _period_from_root(root):
    if root is None:
        return None, None
    if root.tag == ATTACHED_DOCUMENT_TAG:
        tag_attachment = "{%s}Attachment" % CAC
        tag_ext_ref = "{%s}ExternalReference" % CAC
        tag_description = "{%s}Description" % CBC
        attachment = root.find(
            "%s/%s/%s" % (tag_attachment, tag_ext_ref, tag_description)
        )
        inner_xml = attachment.text.strip() if attachment is not None and attachment.text else None
        if inner_xml:
            inner_root = _try_parse(inner_xml)
            if inner_root is not None:
                return _find_period_dates(inner_root)
        return None, None
    if root.tag in DOCUMENT_ROOT_TAGS:
        return _find_period_dates(root)
    return None, None


def extract_period_dates(xml_content):
    """Rango (StartDate, EndDate) del XML DIAN de una nota de credito.

    Retorna (start, end) con el texto de las fechas (p.ej. "2026-09-01") o
    (None, None) si el XML no trae periodo o no es parseable.
    """
    if not xml_content:
        return None, None

    root = _try_parse(xml_content)
    start, end = _period_from_root(root)
    if start or end:
        return start, end

    for inner_root in _collect_embedded_documents(xml_content):
        start, end = _find_period_dates(inner_root)
        if start or end:
            return start, end

    return None, None