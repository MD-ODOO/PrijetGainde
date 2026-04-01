from odoo import api, models


class HrExpenseSheet(models.Model):
    _inherit = "hr.expense.sheet"

    def _get_default_approval_route_for_company(self, company):
        route = self.env.ref(
            "purchase_gainde.approval_route_expense_default_gainde",
            raise_if_not_found=False,
        )
        if route and (not route.company_id or route.company_id.id == company.id):
            return route

        domain = [
            ("model", "=", "hr.expense.sheet"),
            ("company_id", "in", [company.id, False]),
        ]
        return self.env["approval.route"].search(domain, limit=1)

    @api.model_create_multi
    def create(self, vals_list):
        new_vals_list = []
        for vals in vals_list:
            v = dict(vals)
            if not v.get("approval_route_id"):
                company_id = v.get("company_id", self.env.company.id)
                company = self.env["res.company"].browse(company_id)
                route = self._get_default_approval_route_for_company(company)
                if route:
                    v["approval_route_id"] = route.id
            new_vals_list.append(v)
        return super().create(new_vals_list)
