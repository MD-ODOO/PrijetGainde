from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_url_firewall = fields.Boolean(
        string="Activer le firewall URL",
        config_parameter='url_firewall.enable_url_firewall'
    )
