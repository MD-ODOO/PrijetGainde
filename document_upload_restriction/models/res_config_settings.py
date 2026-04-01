from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    allowed_file_extensions = fields.Char(
        string="Extensions autorisées (séparées par des virgules)",
        config_parameter='document_upload_restriction.allowed_file_extensions',
        default="pdf, doc, docx, xls, xlsx, odt, ods, txt, jpg, jpeg, png",
        help="Liste des extensions autorisées, sans point, séparées par des virgules. Exemple : pdf, docx, xlsx",
    )
