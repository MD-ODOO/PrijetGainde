from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    secure_error_enable_js_mask = fields.Boolean(
        string="Masquer les détails techniques côté interface",
        config_parameter='secure_error_handling.enable_js_mask',
        default=True,
    )
    secure_error_generic_message = fields.Char(
        string="Message d’erreur générique",
        config_parameter='secure_error_handling.generic_message',
        default="Une erreur est survenue. Merci de contacter l’administrateur.",
    )