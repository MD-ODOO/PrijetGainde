from odoo import models, fields, _


class ProductTemplate(models.Model):
    _inherit = "product.template"

    asset_count = fields.Integer(string="Assets", compute="_compute_asset_count")

    def _compute_asset_count(self):
        Asset = self.env["asset.management"]
        for product in self:
            variant_ids = product.product_variant_ids.ids
            if variant_ids:
                product.asset_count = Asset.search_count([("product_id", "in", variant_ids)])
            else:
                product.asset_count = 0

    def action_view_assets(self):
        self.ensure_one()
        action = self.env.ref("asset_management.action_assets", raise_if_not_found=False)
        domain = [("product_id", "in", self.product_variant_ids.ids)]
        if action:
            action_vals = action.read()[0]
            action_vals["domain"] = domain
            action_vals["name"] = _("Assets")
            return action_vals
        return {
            "type": "ir.actions.act_window",
            "name": _("Assets"),
            "res_model": "asset.management",
            "view_mode": "list,form",
            "views": [(False, "list"), (False, "form")],
            "domain": domain,
        }
