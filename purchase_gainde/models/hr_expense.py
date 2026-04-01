from odoo import api, models


class HrExpense(models.Model):
    _inherit = "hr.expense"

    @api.onchange("product_id")
    def _gainde_onchange_product_id_compute_analytic(self):
        for expense in self:
            if not expense.product_id:
                continue
            analytic_map = self._gainde_get_analytic_distribution_map(expense)
            if analytic_map:
                expense.analytic_distribution = analytic_map

    @api.model_create_multi
    def create(self, vals_list):
        expenses = super().create(vals_list)
        expenses._gainde_apply_analytic_distribution()
        return expenses

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("skip_gainde_analytic_distribution"):
            return res
        if set(vals.keys()) - {"analytic_distribution"}:
            self._gainde_apply_analytic_distribution()
        return res

    def _gainde_apply_analytic_distribution(self):
        for expense in self:
            if not expense.product_id:
                continue
            analytic_map = expense._gainde_get_analytic_distribution_map(expense)
            if analytic_map:
                expense.with_context(skip_gainde_analytic_distribution=True).write({
                    "analytic_distribution": analytic_map,
                })

    def _gainde_get_analytic_distribution_map(self, expense):
        department = False
        if getattr(expense, "employee_id", False):
            department = getattr(expense.employee_id, "department_id", False)
        helper = self.env["gainde.analytic.distribution.mixin"]
        return helper._gainde_compute_analytic_distribution_map(
            expense.product_id,
            department=department,
        )
