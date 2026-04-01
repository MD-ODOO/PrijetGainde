from odoo import fields, models


class AccountAsset(models.Model):
    _inherit = "account.asset"

    compte_tiers = fields.Char(string="Compte de tiers")
