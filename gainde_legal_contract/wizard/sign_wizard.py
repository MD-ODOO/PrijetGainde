import io
import os
import logging
import tempfile
import requests
import base64
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

_logger = logging.getLogger(__name__)


class SignPincodeWizard(models.TransientModel):
    _name = 'sign.pincode.wizard'
    _description = 'Assistant de signature'

    res_model = fields.Char(required=True)
    res_id = fields.Integer(required=True)
    attachment_id = fields.Many2one('ir.attachment', string="Fichier à signer",
                                    required=True)
    pincode = fields.Char("Code PIN", required=True, password=True)

    def _extract_p12_cert(self):
        """ Convertit le certificat d'authentification société pour Requests """
        company = self.env.company
        if not company.sign_certificate_file:
            raise UserError(
                "Certificat d'authentification API manquant sur la société.")

        p12_data = base64.b64decode(company.sign_certificate_file)
        password = company.sign_certificate_password or ""

        pkey, cert, _ = serialization.pkcs12.load_key_and_certificates(
            p12_data, password.encode(), backend=default_backend()
        )

        # Créer un fichier PEM temporaire (Clé + Cert)
        temp_pem = tempfile.NamedTemporaryFile(delete=False, suffix='.pem')
        with open(temp_pem.name, 'wb') as f:
            f.write(pkey.private_bytes(serialization.Encoding.PEM,
                                       serialization.PrivateFormat.TraditionalOpenSSL,
                                       serialization.NoEncryption()))
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        return temp_pem.name

    def action_confirm_sign(self):
        self.ensure_one()
        user = self.env.user
        record = self.env[self.res_model].browse(self.res_id)

        # 1. Vérifications initiales
        if not user.id_signer or not user.worker_id:
            raise UserError(
                _("Identifiants API manquants sur votre profil utilisateur."))
        if not user.visual_signature:
            raise UserError(
                _("Veuillez uploader votre signature visuelle dans vos préférences."))
        if not self.attachment_id or not self.attachment_id.datas:
            raise UserError(_("Aucun document PDF trouvé pour la signature."))

        # 2. Préparation du binaire (Passage de Base64 à Binary)
        try:
            # On décode le Base64 d'Odoo pour obtenir les bytes PDF
            initial_pdf_bytes = base64.b64decode(self.attachment_id.datas)

            # Application du tampon (on passe des bytes, on reçoit des bytes)
            pdf_stamped_bytes = self.env['abstract.signable.document']._stamp_pdf(initial_pdf_bytes,
                                                user.visual_signature)

            if not pdf_stamped_bytes.startswith(b'%PDF'):
                raise UserError(
                    _("Le fichier généré est corrompu (Header PDF manquant)."))

        except Exception as e:
            _logger.error("Erreur préparation PDF: %s", str(e))
            raise UserError(
                _("Erreur technique lors de la préparation du PDF : %s") % str(
                    e))

        # 3. Extraction du certificat (Doit être au format .pem pour 'requests')
        cert_path = self._extract_p12_cert()

        # 4. Appel API Gaïndé
        api_url = f"https://rasign.gainde2000.sn:8443/app_signatureV1.1/signer/v1.1/sign_document/{user.id_signer}"

        # Paramètres (query) : codePin et workerId
        query_params = {
            'codePin': self.pincode,
            'workerId': user.worker_id
        }

        # Corps (body) : multipart/form-data avec la clé 'filereceivefile'
        files = {
            'filereceivefile': (self.attachment_id.name,
                                io.BytesIO(pdf_stamped_bytes),
                                'application/pdf')
        }

        try:
            response = requests.post(
                api_url,
                params=query_params,
                files=files,
                cert=cert_path,
                timeout=60,
                verify=True
            )

            # Vérification du contenu avant parsing JSON
            if not response.content:
                _logger.error("Gaïndé a renvoyé une réponse vide. Status: %s",
                              response.status_code)
                raise UserError(
                    _("L'API Gaïndé a renvoyé une réponse vide. Vérifiez votre certificat ou code PIN."))

            # Si erreur 400 ou autre, on récupère le message d'erreur détaillé de l'API
            if response.status_code != 200:
                _logger.error("Erreur Gaïndé %s: %s", response.status_code,
                              response.text)
                raise UserError(
                    _("Erreur API Gaïndé (%s) : %s") % (response.status_code,
                                                         response.text))

            # 5. Traitement adaptatif de la réponse (JSON vs Binaire PDF)
            signed_data = False
            content_type = response.headers.get('Content-Type', '').lower()

            # CAS A : C'est un PDF binaire pur (Le flux commence par %PDF)
            if response.content.startswith(b'%PDF'):
                _logger.info("Gaïndé a renvoyé un flux PDF binaire direct.")
                signed_data = base64.b64encode(response.content)

            # CAS B : C'est du JSON
            elif 'application/json' in content_type:
                try:
                    result = response.json()
                    # On extrait la clé, peu importe son nom
                    raw_val = result.get('signedDocument') or result.get(
                        'document') or result.get('data')
                    if raw_val:
                        signed_data = raw_val
                except Exception as e:
                    _logger.error("Échec lecture JSON Gaïndé: %s", str(e))

            # CAS C : C'est peut-être du Base64 brut (Texte sans JSON)
            if not signed_data:
                potential_b64 = response.content.strip()
                try:
                    # Si on peut le décoder et que ça donne un PDF, c'était du B64 brut
                    decoded_test = base64.b64decode(potential_b64,
                                                    validate=True)
                    if decoded_test.startswith(b'%PDF'):
                        _logger.info("Gaïndé a renvoyé du Base64 brut.")
                        signed_data = potential_b64
                except Exception:
                    pass

                # CAS DE SECOURS / ERREUR CRITIQUE
                if not signed_data:
                    # On log les 500 premiers caractères pour voir si c'est du HTML (Erreur serveur)
                    _logger.error("FORMAT INCONNU REÇU : %s",
                                  response.text[:500])
                    raise UserError(
                        _("Le serveur Gaïndé a répondu dans un format non reconnu.\n\nDébut de réponse : %s") % response.text[
                            :150])

            # 6. Création de l'attachement final et mise à jour
            new_attach = self.env['ir.attachment'].create({
                'name': f"{self.attachment_id.name.replace('.pdf', '')}_signe.pdf",
                'datas': signed_data,
                'res_model': self.res_model,
                'res_id': self.res_id,
                'type': 'binary',
                'mimetype': 'application/pdf',
            })

            # Classification Documents
            if hasattr(self.env['documents.document'], 'classify_attachment'):
                self.env['documents.document'].classify_attachment(
                    new_attach.id, self.res_model, self.res_id)

            # Mise à jour du document parent
            record.write({'sign_status': 'signed'})
            record.message_post(body=_("Document signé électroniquement via "
                                       "Gaïndé par %s.") % user.name)

            return {'type': 'ir.actions.act_window_close'}

        except requests.exceptions.RequestException as e:
            _logger.error("Erreur de connexion Gaïndé: %s", str(e))
            raise UserError(
                _("Erreur de communication avec Gaïndé : %s") % str(e))
        except Exception as e:
            _logger.error("Erreur imprévue : %s", str(e))
            raise UserError(
                _("Erreur lors du traitement de la signature : %s") % str(e))
        finally:
            # Nettoyage du certificat temporaire
            if cert_path and os.path.exists(cert_path):
                os.remove(cert_path)
