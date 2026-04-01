import os

from odoo import api, models, _
from odoo.exceptions import UserError

class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model
    def create(self, vals):
        self._check_file_extension(vals)
        return super().create(vals)

    def write(self, vals):
        self._check_file_extension(vals)
        return super().write(vals)

    def _check_file_extension(self, vals):
        # On ne vérifie que si un fichier est réellement uploadé
        if not vals.get('datas') and not vals.get('url') and not vals.get('name'):
            return

        # Nom du fichier
        filename = vals.get('name') or (self[:1].name if self else '')
        if not filename:
            return

        # Extension extraite
        _, ext = os.path.splitext(filename)
        ext = (ext or '').lower().lstrip('.')

        if not ext:
            raise UserError(_("Le fichier doit avoir une extension valide."))

        # Récupération de la liste blanche depuis ir.config_parameter
        icp = self.env['ir.config_parameter'].sudo()
        allowed = icp.get_param(
            'document_upload_restriction.allowed_file_extensions',
            'pdf, doc, docx, xls, xlsx, odt, ods, txt, jpg, jpeg, png',
        )

        allowed_list = [
            e.strip().lower()
            for e in allowed.split(',')
            if e.strip()
        ]

        if allowed_list and ext not in allowed_list:
            raise UserError(_(
                "Le fichier « %s » a une extension non autorisée (%s).\n"
                "Extensions autorisées : %s"
            ) % (filename, ext, ', '.join(allowed_list)))
