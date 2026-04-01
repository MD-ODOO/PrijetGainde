from odoo import models, fields, _


class StockPicking(models.Model):
    _inherit = "stock.picking"

    asset_ids = fields.Many2many(
        "asset.management",
        "stock_picking_asset_rel",
        "picking_id",
        "asset_id",
        string="Assets",
        readonly=True,
    )
    asset_count = fields.Integer(string="Assets", compute="_compute_asset_count")

    def _compute_asset_count(self):
        for picking in self:
            picking.asset_count = len(picking.asset_ids)

    def action_view_assets(self):
        self.ensure_one()
        
        # Si un seul actif, ouvrir en vue formulaire
        if len(self.asset_ids) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Actif"),
                "res_model": "asset.management",
                "view_mode": "form",
                "res_id": self.asset_ids.id,
                "views": [(False, "form")],
            }
        
        # Si plusieurs actifs, ouvrir en vue liste
        action = self.env.ref("asset_management.action_assets", raise_if_not_found=False)
        if action:
            action_vals = action.read()[0]
            action_vals["domain"] = [("id", "in", self.asset_ids.ids)]
            action_vals["name"] = _("Actifs")
            return action_vals
        return {
            "type": "ir.actions.act_window",
            "name": _("Actifs"),
            "res_model": "asset.management",
            "view_mode": "list,form",
            "views": [(False, "list"), (False, "form")],
            "domain": [("id", "in", self.asset_ids.ids)],
        }

