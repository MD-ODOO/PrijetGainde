from odoo import models, fields


class TreasuryInvoiceTemplateLine(models.Model):
    _name = "treasury.invoice.template.line"
    _description = "Ligne de modèle de facture client"

    template_id = fields.Many2one("treasury.invoice.template", required=True, ondelete="cascade", string="Modèle")
    product_id = fields.Many2one("product.product", string="Produit")
    name = fields.Char(string="Description")
    quantity = fields.Float(default=1.0)
    price_unit = fields.Float(string="Prix unitaire")
    tax_ids = fields.Many2many("account.tax", string="Taxes")
