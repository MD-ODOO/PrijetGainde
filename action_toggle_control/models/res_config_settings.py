from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_action_48 = fields.Boolean(
        string="Activer l'accès à l'action 48",
        config_parameter='action_toggle_control.enable_action_48'
    )
