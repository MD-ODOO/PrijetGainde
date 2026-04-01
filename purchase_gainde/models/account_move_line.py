from odoo import api, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.onchange("product_id")
    def _gainde_onchange_product_id_compute_analytic(self):
        for line in self:
            if not line.product_id or line.display_type:
                continue
            analytic_map = self._gainde_get_analytic_distribution_map(line)
            if analytic_map:
                line.analytic_distribution = analytic_map

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._gainde_apply_analytic_distribution()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("skip_gainde_analytic_distribution"):
            return res
        if set(vals.keys()) - {"analytic_distribution"}:
            self._gainde_apply_analytic_distribution()
        return res

    def _gainde_apply_analytic_distribution(self):
        invoice_types = {
            "out_invoice",
            "out_refund",
            "in_invoice",
            "in_refund",
            "in_receipt",
            "out_receipt",
        }
        for line in self:
            if line.display_type or not line.product_id:
                continue
            if line.move_id and line.move_id.move_type not in invoice_types:
                continue
            analytic_map = line._gainde_get_analytic_distribution_map(line)
            if analytic_map:
                line.with_context(skip_gainde_analytic_distribution=True).write({
                    "analytic_distribution": analytic_map,
                })

    def _gainde_get_analytic_distribution_map(self, line):
        department = False
        if getattr(line, "purchase_line_id", False) and line.purchase_line_id.order_id:
            order = line.purchase_line_id.order_id
            department = getattr(order, "department_id", False)
        helper = self.env["gainde.analytic.distribution.mixin"]
        return helper._gainde_compute_analytic_distribution_map(
            line.product_id,
            department=department,
        )
