import frappe


def execute():
    DEFAULT_CONFIG = [
        {"code": "basic", "tab_label": u"Informaci\u00f3n B\u00e1sica", "tab_group": "basic", "tab_order": 1, "show_in_wizard": 1, "has_finish_button": 0},
        {"code": "address", "tab_label": u"Direcciones", "tab_group": "address", "tab_order": 2, "show_in_wizard": 1, "has_finish_button": 0},
        {"code": "contact", "tab_label": "Contactos", "tab_group": "contact", "tab_order": 3, "show_in_wizard": 1, "has_finish_button": 0},
        {"code": "legal", "tab_label": u"Representante Legal", "tab_group": "legal", "tab_order": 4, "show_in_wizard": 1, "has_finish_button": 0},
        {"code": "bank_account", "tab_label": u"Cuentas Bancarias", "tab_group": "bank_account", "tab_order": 5, "show_in_wizard": 1, "has_finish_button": 0},
        {"code": "bank_account_complement", "tab_label": "", "tab_group": "bank_account", "tab_order": 0, "show_in_wizard": 0, "has_finish_button": 0},
        {"code": "tax", "tab_label": u"Informaci\u00f3n Tributaria", "tab_group": "tax", "tab_order": 6, "show_in_wizard": 1, "has_finish_button": 0},
        {"code": "financial", "tab_label": u"Informaci\u00f3n Financiera", "tab_group": "financial", "tab_order": 7, "show_in_wizard": 1, "has_finish_button": 0},
        {"code": "international", "tab_label": u"Operaciones Internacionales", "tab_group": "international", "tab_order": 8, "show_in_wizard": 1, "has_finish_button": 0},
        {"code": "shareholder", "tab_label": u"Accionistas y Asociados", "tab_group": "shareholder", "tab_order": 9, "show_in_wizard": 1, "has_finish_button": 0},
        {"code": "document", "tab_label": "Documentos", "tab_group": "document", "tab_order": 10, "show_in_wizard": 1, "has_finish_button": 1},
    ]

    for config in DEFAULT_CONFIG:
        if not frappe.db.exists("qp_SP_FieldSection", config["code"]):
            continue

        section = frappe.get_doc("qp_SP_FieldSection", config["code"])
        section.tab_label = config["tab_label"]
        section.tab_group = config["tab_group"]
        section.tab_order = config["tab_order"]
        section.show_in_wizard = config["show_in_wizard"]
        section.has_finish_button = config["has_finish_button"]
        section.save()

    frappe.db.commit()
