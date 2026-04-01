from odoo import models, fields

class ResUsers(models.Model):
    _inherit = "res.users"

    allowed_analytic_account_ids = fields.Many2many(
        'account.analytic.account',
        string="Authorized Analytic Accounts",
        help="Restricts accounting visibility to these analytic accounts."
    )