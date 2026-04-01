from odoo import models, fields, _


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    asset_count = fields.Integer(string="Actifs", compute="_compute_asset_count")

    def _compute_asset_count(self):
        Asset = self.env["asset.management"]
        for employee in self:
            employee.asset_count = Asset.search_count([
                ("transfer_ids.transfer_employee_id", "=", employee.id),
                ("transfer_ids.status", "=", "assigned"),
            ])

    def action_view_assets(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Actifs"),
            "res_model": "asset.management",
            "view_mode": "list,form",
            "views": [(False, "list"), (False, "form")],
            "domain": [
                ("transfer_ids.transfer_employee_id", "=", self.id),
                ("transfer_ids.status", "=", "assigned"),
            ],
        }
        return action
