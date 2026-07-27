---
name: allowance-charge-extraction
description: >-
  Use when implementing, debugging, or extending the extraction of document-level
  AllowanceCharge from DIAN electronic invoice XML (CreditNote, DebitNote,
  Invoice). Covers both direct XML parsing and AttachedDocument wrapper unwrapping,
  the recursive tree traversal that skips *Line branches, field mapping to
  qp_SP_AllowanceCharge, the full data flow from middleware API to persistence,
  and how to test with real documents. Use ONLY when the task involves XML parsing
  of DIAN UBL documents for AllowanceCharge data, NOT for supplier editing, PO sync,
  or bank normalization.
---

# AllowanceCharge Extraction (CreditNote / DebitNote / Invoice)

## Arquitectura

```
middleware API (lAttached)
  → services/document_sync.py: create_document_detail()
      → _create_allowance_charges_from_xml()
          → services/xml_allowance_charge.py: extract_document_allowance_charges()
              → _find_document_level_charges()  ← traversal recursivo
  → qp_SP_DocumentDetail.allowance_charges (child table qp_SP_AllowanceCharge)
```

## Document root tags soportados

| Tipo | Clark notation |
|------|---------------|
| **CreditNote** | `{urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2}CreditNote` |
| **DebitNote** | `{urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2}DebitNote` |
| **Invoice** | `{urn:oasis:names:specification:ubl:schema:xsd:Invoice-2}Invoice` |
| **AttachedDocument** | `{urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2}AttachedDocument` ← wrapper |

## Estructura del XML real

### Caso A: Documento directo (ej: documentdetail.xml de prueba)

```xml
<CreditNote xmlns="urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2" ...>
  <cac:AllowanceCharge>  ← document-level, se captura
    <cbc:ChargeIndicator>false</cbc:ChargeIndicator>
    <cbc:AllowanceChargeReasonCode>09</cbc:AllowanceChargeReasonCode>
    <cbc:AllowanceChargeReason>DESCUENTO GENERAL</cbc:AllowanceChargeReason>
    <cbc:MultiplierFactorNumeric>0.31</cbc:MultiplierFactorNumeric>
    <cbc:Amount currencyID="COP">5920.00</cbc:Amount>
    <cbc:BaseAmount currencyID="COP">1865920.00</cbc:BaseAmount>
  </cac:AllowanceCharge>
  ...
  <cac:CreditNoteLine>
    <cac:AllowanceCharge>  ← line-level, se ignora
      ...
    </cac:AllowanceCharge>
  </cac:CreditNoteLine>
</CreditNote>
```

### Caso B: Envuelto en AttachedDocument (caso real del middleware)

```xml
<AttachedDocument ...>
  ...
  <cac:Attachment>
    <cac:ExternalReference>
      <cbc:Description>
        <?xml version="1.0" encoding="utf-8"?>
        <Invoice ...>   ← documento real embebido como texto
          <cac:AllowanceCharge>...</cac:AllowanceCharge>
        </Invoice>
      </cbc:Description>
    </cac:ExternalReference>
  </cac:Attachment>
  ...
</AttachedDocument>
```

El documento real está embebido como texto plano XML dentro de:
`cac:Attachment/cac:ExternalReference/cbc:Description`

## Lógica de extracción

```python
def extract_document_allowance_charges(xml_content):
    root = ET.fromstring(xml_content)

    # Caso A: root directo (CreditNote/DebitNote/Invoice)
    if root.tag in DOCUMENT_ROOT_TAGS:
        return _find_document_level_charges(root)

    # Caso B: AttachedDocument wrapper
    if root.tag == ATTACHED_DOCUMENT_TAG:
        inner_xml = _extract_embedded_document(root)
        if inner_xml:
            inner_root = ET.fromstring(inner_xml)
            if inner_root.tag in DOCUMENT_ROOT_TAGS:
                return _find_document_level_charges(inner_root)

    return []
```

El `_find_document_level_charges` recorre recursivamente el árbol XML pero **salta** cualquier rama `CreditNoteLine`, `DebitNoteLine` o `InvoiceLine` (definidas en `LINE_TAGS`) para no capturar AllowanceCharge de nivel línea.

## Campos extraídos → qp_SP_AllowanceCharge

| Tag XML | fieldname en doctype | type |
|---------|---------------------|------|
| `cbc:ChargeIndicator` | `charge_indicator` | Check (1=true, 0=false) |
| `cbc:AllowanceChargeReasonCode` | `reason_code` | Data |
| `cbc:AllowanceChargeReason` | `reason` | Data |
| `cbc:MultiplierFactorNumeric` | `multiplier_factor` | Float |
| `cbc:Amount/@currencyID` + text | `amount`, `currency` | Currency + Data |
| `cbc:BaseAmount` | `base_amount` | Currency |

## Archivos clave

| Archivo | Rol |
|---------|-----|
| `services/xml_allowance_charge.py` | Parseo puro (sin `import frappe`) |
| `services/document_sync.py` | Integración en flujo de sincronización (`_create_allowance_charges_from_xml`) |
| `doctype/qp_sp_allowancecharge/qp_sp_allowancecharge.json` | Child table Doctype |
| `doctype/qp_sp_allowancecharge/qp_sp_allowancecharge.py` | Clase Python del Doctype |
| `doctype/qp_sp_documentdetail/qp_sp_documentdetail.json` | Parent con field `allowance_charges` (Table) |

## Cómo probar

1. Limpiar datos viejos:
```sql
SET SQL_SAFE_UPDATES = 0;
DELETE FROM `tabqp_SP_DetailLineTax` WHERE parent IN (SELECT name FROM `tabqp_SP_DetailLine`);
DELETE FROM `tabqp_SP_DetailLine` WHERE parenttype = 'qp_SP_DocumentDetail';
DELETE FROM `tabqp_SP_DocumentAttach` WHERE parenttype = 'qp_SP_DocumentDetail';
DELETE FROM `tabqp_SP_EventLog` WHERE parenttype = 'qp_SP_DocumentDetail';
DELETE FROM `tabqp_SP_AllowanceCharge` WHERE parenttype = 'qp_SP_DocumentDetail';
DELETE FROM `tabFile` WHERE attached_to_doctype = 'qp_SP_DocumentDetail';
DELETE FROM `tabqp_SP_DocumentDetail`;
UPDATE `tabqp_SP_DocumentSyncLine` SET is_completed = 0 WHERE is_completed = 1;
```

2. Resincronizar:
```bash
bench --site front_supplier_cm_admin execute qp_supplier_front.uses_cases.documents.sync_by_supplier.sync
bench --site front_supplier_cm_admin execute qp_supplier_front.uses_cases.documents.sync_detail.sync
```

3. Verificar datos guardados:
```sql
SELECT parent, charge_indicator, reason_code, reason, amount, currency
FROM `tabqp_SP_AllowanceCharge`;
```

## Consideraciones

- El namespace URI es el mismo para `cac` y `cbc` en todos los tipos de documento (CreditNote, DebitNote, Invoice)
- Se usa Clark notation `{uri}tag` en vez de prefijos con `NS` dict, porque `findall` con prefijos no es consistente entre versiones de ElementTree
- El `AttachedDocument` usa `ExternalReference` con el XML en `Description` (no `EmbeddedDocumentBinaryObject`)
- Para agregar un nuevo tipo de documento, solo hay que agregar su root tag a `DOCUMENT_ROOT_TAGS` y su line tag a `LINE_TAGS`
