from frappe.model.document import Document

class qp_SP_DocumentDetail(Document):
    def before_insert(self):
        if not self.nvpro_ndoc:
            self.name = "SP:{}".format(self.nvfac_nume or "")
