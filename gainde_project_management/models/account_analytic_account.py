from odoo import models, fields

class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    budget_line_ids = fields.One2many(
        'budget.line',
        'account_id',
        string='Lignes Budgétaires'
    )
