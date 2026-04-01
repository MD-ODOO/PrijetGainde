from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    tier_account = fields.Char(
        string='Compte Tiers',
        related='partner_id.tier_account',
        readonly=True,
    )
