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

LINE_TAGS = frozenset([
    "{%s}CreditNoteLine" % CAC,
    "{%s}DebitNoteLine" % CAC,
    "{%s}InvoiceLine" % CAC,
])


def _parse_allowance_charge(ac):
    charge = {}
    indicator = ac.find("{%s}ChargeIndicator" % CBC)
    if indicator is not None:
        charge["charge_indicator"] = 1 if indicator.text == "true" else 0
    reason_code = ac.find("{%s}AllowanceChargeReasonCode" % CBC)
    if reason_code is not None:
        charge["reason_code"] = reason_code.text
    reason = ac.find("{%s}AllowanceChargeReason" % CBC)
    if reason is not None:
        charge["reason"] = reason.text
    multiplier = ac.find("{%s}MultiplierFactorNumeric" % CBC)
    if multiplier is not None:
        charge["multiplier_factor"] = float(multiplier.text)
    amount_el = ac.find("{%s}Amount" % CBC)
    if amount_el is not None:
        charge["amount"] = float(amount_el.text)
        currency = amount_el.get("currencyID")
        if currency:
            charge["currency"] = currency
    base_el = ac.find("{%s}BaseAmount" % CBC)
    if base_el is not None:
        charge["base_amount"] = float(base_el.text)
    return charge


def _find_document_level_charges(element):
    tag_ac = "{%s}AllowanceCharge" % CAC
    charges = []
    for child in element:
        if child.tag in LINE_TAGS:
            continue
        if child.tag == tag_ac:
            charges.append(_parse_allowance_charge(child))
        charges.extend(_find_document_level_charges(child))
    return charges


def _extract_embedded_document(root):
    tag_attachment = "{%s}Attachment" % CAC
    tag_ext_ref = "{%s}ExternalReference" % CAC
    tag_description = "{%s}Description" % CBC

    attachment = root.find("%s/%s/%s" % (tag_attachment, tag_ext_ref, tag_description))
    if attachment is not None and attachment.text:
        return attachment.text.strip()
    return None


def extract_document_allowance_charges(xml_content):
    root = ET.fromstring(xml_content)

    if root.tag in DOCUMENT_ROOT_TAGS:
        return _find_document_level_charges(root)

    if root.tag == ATTACHED_DOCUMENT_TAG:
        inner_xml = _extract_embedded_document(root)
        if inner_xml:
            inner_root = ET.fromstring(inner_xml)
            if inner_root.tag in DOCUMENT_ROOT_TAGS:
                return _find_document_level_charges(inner_root)

    return []
