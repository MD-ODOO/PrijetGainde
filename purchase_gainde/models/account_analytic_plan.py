from odoo import models, api
from odoo.exceptions import ValidationError


class AccountAnalyticPlan(models.Model):
    _inherit = "account.analytic.plan"

    _sql_constraints = [
        (
            "analytic_plan_name_unique",
            "unique(name)",
            "Le nom du plan analytique doit être unique.",
        ),
    ]

    @api.constrains("is_budgetary_poste", "is_budgetary_center")
    def _check_exclusive_budget_flags(self):
        for rec in self:
            if rec.is_budgetary_poste and rec.is_budgetary_center:
                raise ValidationError(
                    "Un enregistrement ne peut pas être à la fois 'poste' et 'centre budgétaire'."
                )

    @api.model
    def ensure_budget_plans(self):
        """Créer les plans analytiques requis s'ils n'existent pas."""
        plans = [
            "Centres budgétaires",
            "Postes budgétaires",
        ]
        for name in plans:
            if not self.sudo().search([("name", "=", name)], limit=1):
                self.sudo().create({"name": name})
        return True
