from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_ninea = fields.Char(string='NINEA')
