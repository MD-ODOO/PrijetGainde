import io
import base64
import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError
try:
    import fitz # PyMuPDF
except ImportError:
    fitz = None

import logging

_logger = logging.getLogger(__name__)

# Vérification des dépendances Python
try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    from cryptography.x509.oid import NameOID
except ImportError:
    _logger.warning("La bibliothèque 'cryptography' est manquante.")

try:
    from endesive.pdf import cms
except ImportError:
    _logger.warning("La bibliothèque 'endesive' est manquante.")


class AbstractSignableDocument(models.AbstractModel):
    _name = 'abstract.signable.document'
    _description = 'Mixin pour Signature Électronique GED'

    sign_request_id = fields.Many2one('sign.request',
                                      string="Requête de Signature",
                                      readonly=True, tracking=True)

    # Harmonisation du statut avec vos vues XML
    sign_status = fields.Selection([
        ('draft', 'Brouillon'),
        ('sent', 'Envoyé'),
        ('signed', 'Signé'),
        ('refused', 'Refusé'),
        ('expired', 'Expiré'),
    ], string="Statut Signature", default='draft', readonly=True,
        tracking=True)

    # Note : Le modèle 'sign.certificate' doit exister ou être créé dans votre module
    sign_certificate_id = fields.Many2one('res.company',
                                          string="Certificat Société",
                                          default=lambda
                                              self: self.env.company)

    @api.model
    def _get_default_certificate(self):
        """ Récupère le certificat global par défaut """
        return self.env['sign.certificate'].search(
            [('company_id', '=', self.env.company.id)], limit=1)

    def _get_signable_attachment(self):
        """ Cherche le PDF dans les pièces jointes ou le génère si c'est un rapport """
        self.ensure_one()
        # --- CAS 1 : Utilisation de document_ids (tes modèles legal_*) ---
        if hasattr(self, 'document_ids') and self.document_ids:
            # On cherche le premier PDF dans les documents liés
            doc = self.document_ids.filtered(
                lambda d: d.mimetype == 'application/pdf')[:1]
            if doc:
                # Si c'est un record de 'documents.document', on retourne son 'attachment_id'
                return doc.attachment_id if hasattr(doc,
                                                    'attachment_id') else doc

        # --- CAS 2 : Recherche dans les pièces jointes standards (Chatter) ---
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('mimetype', '=', 'application/pdf')
        ], limit=1, order='create_date desc')

        if attachment:
            return attachment

        # --- CAS 3 : Génération automatique si rien n'est trouvé ---
        report_name = self._get_report_name()
        if report_name:
            pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
                report_name, self.id)
            return self.env['ir.attachment'].create({
                'name': f"{self.display_name}.pdf",
                'datas': base64.b64encode(pdf_content),
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'application/pdf'
            })

        return False

    def _get_report_name(self):
        """
        Retourne dynamiquement le rapport de l'objet actuel.
        On cherche le rapport par défaut défini pour le modèle.
        """
        report = self.env['ir.actions.report'].search([
            ('model', '=', self._name),
            ('report_type', '=', 'qweb-pdf')
        ], limit=1)
        return report.report_name if report else False

    # def action_sign_document(self):
    #     """ Action générique pour signer n'importe quel doc lié """
    #     self.ensure_one()
    #
    #     if self.sign_status == 'signed':
    #         raise UserError(_("Ce document est déjà signé."))
    #
    #     company = self.env.company
    #     # 1 Récupération du certificat depuis la Société
    #     if not company.sign_certificate_file:
    #         raise UserError(
    #             _("Veuillez configurer le certificat PKCS12 sur la société."))
    #
    #     p12_data = base64.b64decode(company.sign_certificate_file)
    #     p12_password = company.sign_certificate_password.encode(
    #         'utf-8') if company.sign_certificate_password else None
    #
    #     try:
    #         pkey_obj, cert_obj, additional_certs_objs = serialization.pkcs12.load_key_and_certificates(
    #             p12_data, p12_password, backend=default_backend())
    #
    #     except Exception as e:
    #         raise UserError(
    #             _("Erreur de chargement du certificat : %s") % str(e))
    #
    #     # 2. CONVERSION CRITIQUE : Transformer les objets en format PEM Bytes (Nécessaire pour Endesive)
    #     try:
    #         # Clé privée en PEM
    #         p12_key_pem = pkey_obj.private_bytes(
    #             encoding=serialization.Encoding.PEM,
    #             format=serialization.PrivateFormat.TraditionalOpenSSL,
    #             encryption_algorithm=serialization.NoEncryption()
    #         )
    #         # Certificat en PEM
    #         p12_cert_pem = cert_obj.public_bytes(serialization.Encoding.PEM)
    #
    #         # Chaîne de certificats (optionnel) en PEM
    #         additional_certs_pem = []
    #         if additional_certs_objs:
    #             for cert in additional_certs_objs:
    #                 additional_certs_pem.append(
    #                     cert.public_bytes(serialization.Encoding.PEM))
    #
    #     except Exception as e:
    #         raise UserError(
    #             _("Erreur de formatage des clés pour signature : %s") % str(e))
    #
    #     # 3. Récupération du PDF à signer
    #     attachment = self._get_signable_attachment()
    #     if not attachment:
    #         raise UserError(_("Aucun PDF signable trouvé."))
    #
    #     pdf_bytes = base64.b64decode(attachment.datas)
    #     date_str = datetime.datetime.now().strftime('%Y%m%d%H%M%S+00\'00\'')
    #
    #     # 4. Extraction du Common Name (CN) du certificat
    #     try:
    #         common_name = \
    #             cert_obj.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[
    #                 0].value
    #     except:
    #         common_name = company.name
    #
    #     dct = {
    #         'aligned': 0,
    #         'contact': self.env.user.email or company.email,
    #         'location': 'Dakar, Sénégal',
    #         'signingdate': date_str.encode(),
    #         'reason': _('Signature Juridique - %s') % self.display_name,
    #         'name': common_name,
    #     }
    #
    #     # 5. Signature avec Endesive (On passe les PEM Bytes, pas les objets Python)
    #     try:
    #         signed_pdf = cms.sign(pdf_bytes, dct, p12_key_pem, p12_cert_pem,
    #                               additional_certs_pem, 'sha256')
    #     except Exception as e:
    #         raise UserError(
    #             _("Erreur lors de la signature Endesive : %s") % str(e))
    #
    #     signed_attachment = self.env['ir.attachment'].create({
    #         'name': attachment.name.replace('.pdf', '') + '_signe.pdf',
    #         'datas': base64.b64encode(signed_pdf),
    #         'mimetype': 'application/pdf',
    #         'res_model': self._name,
    #         'res_id': self.id,
    #     })
    #
    #     self.env['documents.document'].classify_attachment(signed_attachment.id,
    #                                                        self._name, self.id)
    #     self.write({'sign_status': 'signed'})
    #
    #     # Callback pour changer d'étape (si défini dans legal_contract par ex)
    #     if hasattr(self, '_update_stage_after_sign'):
    #         self._update_stage_after_sign()
    #
    #     return {
    #         'type': 'ir.actions.act_url',
    #         'url': f"/web/content/{signed_attachment.id}?download=true",
    #         'target': 'self',
    #     }

    def _stamp_pdf(self, pdf_binary, img_b64):
        """ Insère l'image visuelle sur la dernière page.
            Prend des 'bytes' en entrée pour le PDF. """
        if not fitz: raise UserError("Installez pymupdf sur le serveur.")

        # On utilise directement pdf_binary (déjà décodé par l'appelant)
        doc = fitz.open(stream=pdf_binary, filetype="pdf")

        # L'image est souvent stockée en b64 dans Odoo, on la décode ici
        img_data = base64.b64decode(img_b64)
        # Dernière page
        page = doc[-1]
        # Position du tampon
        rect = fitz.Rect(page.rect.width - 170, page.rect.height - 250,
                         page.rect.width - 20, page.rect.height - 175)

        # PyMuPDF peut prendre les bytes directement avec 'stream'
        page.insert_image(rect, stream=img_data)

        # Extraction des bytes du PDF modifié
        output_bytes = doc.write()
        doc.close()
        return output_bytes

    def action_sign_document(self):
        """ Ouvre le wizard pour la saisie du PIN """

        self.ensure_one()

        # On cherche le PDF le plus récent pour le suggérer par défaut
        last_pdf = self.env['ir.attachment'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('mimetype', '=', 'application/pdf')
        ], limit=1, order='create_date desc')

        return {
            'name': _('Sélection du document et Signature'),
            'type': 'ir.actions.act_window',
            'res_model': 'sign.pincode.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
                'default_attachment_id': last_pdf.id if last_pdf else False,
            }
        }

    @api.model_create_multi
    def create(self, vals_list):
        """ Synchronisation à la création """
        records = super().create(vals_list)

        if self._name != 'documents.document':
            # Et on vérifie que le modèle possède bien le champ document_ids
            if hasattr(self, 'document_ids'):
                for record in records:
                    if record.document_ids:
                        for att in record.document_ids:
                            # Synchronisation
                            self.env['documents.document'].classify_attachment(
                                att.id, record._name, record.id
                            )
        return records

    def write(self, vals):
        """ Synchronisation lors de la modification (ajout de fichiers)"""
        res = super().write(vals)
        if self._name != 'documents.document' and 'document_ids' in vals:
            for record in self:
                # On rafraîchit pour avoir les valeurs à jour
                record.invalidate_recordset()
                if hasattr(record, 'document_ids') and record.document_ids:
                    for att in record.document_ids:
                        # Synchronisation
                        self.env['documents.document'].classify_attachment(
                            att.id, record._name, record.id
                        )
        return res

    # def _get_signable_attachment(self):
    #     """ Méthode à surcharger par modèle : retourne l'attachment PDF principal """
    #     raise NotImplementedError(
    #         _("Implémentez _get_signable_attachment pour ce modèle."))

    def _update_stage_after_sign(self):
        """ Optionnel : surcharge par modèle pour changer stage après signature """
        pass
