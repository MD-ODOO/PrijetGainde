from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64

# Import pour la validation réelle
try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
except ImportError:
    serialization = None


class ResCompany(models.Model):
    _inherit = 'res.company'

    sign_certificate_file = fields.Binary(
        string="Certificat Signature (.p12/.pfx)", attachment=True)
    sign_certificate_filename = fields.Char(string="Nom fichier certificat")
    sign_certificate_password = fields.Char(string="Mot de passe certificat",
                                            groups="base.group_system")

    def action_test_certificate(self):
        self.ensure_one()
        if not self.sign_certificate_file:
            raise UserError(
                _("Veuillez d'abord uploader un fichier de certificat."))

        if not serialization:
            raise UserError(
                _("La bibliothèque 'cryptography' n'est pas installée sur le serveur."))

        try:
            p12_data = base64.b64decode(self.sign_certificate_file)
            password = self.sign_certificate_password.encode(
                'utf-8') if self.sign_certificate_password else None

            # Tentative de lecture réelle du certificat
            serialization.pkcs12.load_key_and_certificates(
                p12_data, password, backend=default_backend()
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Certificat Valide'),
                    'message': _(
                        'Le certificat %s a été déchiffré avec succès.') % self.sign_certificate_filename,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            raise UserError(_("Échec de la validation : %s") % str(e))
