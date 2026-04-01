from odoo import _, api, fields, models


class PurchaseRequestLine(models.Model):
    _inherit = 'purchase.request.line'

    portal_product_description = fields.Char('Portal product description')

    @api.onchange("product_id")
    def onchange_product_id(self):
        if self.product_id:
            if self.portal_product_description:
                name = self.product_id.name
                if self.product_id.code:
                    name = f"[{self.product_id.code}] {name}"
                if self.product_id.description_purchase:
                    name += "\n" + self.product_id.description_purchase
                self.product_uom_id = self.product_id.uom_id.id
                self.name = name
            else:
                super().onchange_product_id()
