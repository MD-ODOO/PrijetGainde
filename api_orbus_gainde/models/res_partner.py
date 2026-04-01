from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    orbus_customer = fields.Boolean(
        string="Client Orbus",
        default=False,
        help="Coché pour les clients créés via l'API Orbus.",
    )
