from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    center_id = fields.Many2one(
        comodel_name="account.analytic.account",
        string="Centre budgétaire",
        domain=[("is_budgetary_center", "=", True)],
        help="Centre budgétaire lié au produit (utilisé pour la distribution analytique sur les ventes)",
    )


class ProductProduct(models.Model):
    _inherit = "product.product"

    center_id = fields.Many2one(
        related="product_tmpl_id.center_id",
        string="Centre budgétaire",
        store=True,
        readonly=False,
        help="Centre budgétaire lié à la variante produit (hérité du produit).",
    )
