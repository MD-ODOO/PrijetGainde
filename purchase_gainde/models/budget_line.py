from odoo import models, fields


class BudgetLine(models.Model):
    _inherit = "budget.line"

    analytic_code = fields.Char(string="Code analytique")

    # Montant validé (snapshot de budget_amount au moment de la révision)
    revised_budget = fields.Float(string="Validé")
