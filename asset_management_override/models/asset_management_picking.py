from odoo import models, fields, _


class AssetManagement(models.Model):
    _inherit = "asset.management"

    picking_ids = fields.Many2many(
        "stock.picking",
        "stock_picking_asset_rel",
        "asset_id",
        "picking_id",
        string="Stock Pickings",
        readonly=True,
    )
    picking_count = fields.Integer(string="Réceptions", compute="_compute_picking_count")

    def _compute_picking_count(self):
        for asset in self:
            asset.picking_count = len(asset.picking_ids)

    def action_view_pickings(self):
        self.ensure_one()
        action = self.env.ref("stock.action_picking_tree_all", raise_if_not_found=False)
        if action:
            action_vals = action.read()[0]
            action_vals["domain"] = [("id", "in", self.picking_ids.ids)]
            action_vals["name"] = _("Réceptions")
            return action_vals
        return {
            "type": "ir.actions.act_window",
            "name": _("Réceptions"),
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "views": [(False, "list"), (False, "form")],
            "domain": [("id", "in", self.picking_ids.ids)],
        }
