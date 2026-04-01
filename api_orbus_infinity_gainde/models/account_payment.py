import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    orbus_infinity_reference_panier = fields.Char(
        string="Référence panier Orbus Infinity",
        help="Identifiant du panier Orbus Infinity (referencePanier).",
    )

    def action_post(self):
        """Surcharge du post Odoo pour brancher Orbus Infinity.

        - Si le paiement est de type Orbus Infinity, on appelle d'abord
          l'API Infinity (detail-panier + payer), puis on laisse Odoo
          poster normalement.
        - Sinon, on délègue au module précédent (Classic / standard).
        """
        infinity_payments = self.filtered(lambda p: p.orbus_payment_type == "infinity")

        for payment in infinity_payments:
            if not payment.orbus_infinity_reference_panier:
                raise UserError(_("Veuillez renseigner la référence panier Orbus Infinity."))

            config = payment.env["orbus.infinity.api.config"].get_config_for_company(payment.company_id)

            # Recharger le panier si besoin
            panier_data = {}
            if payment.orbus_raw_response:
                try:
                    panier_data = json.loads(payment.orbus_raw_response)
                except Exception:  # pragma: no cover
                    panier_data = {}

            if not panier_data:
                panier_data = config.api_detail_panier(
                    referencePanier=payment.orbus_infinity_reference_panier
                )

                config._create_api_attachment(
                    payment,
                    "detail-panier",
                    "GET",
                    f"{config.gateway_url}/detail-panier",
                    {"referencePanier": payment.orbus_infinity_reference_panier},
                    panier_data,
                )

                # Stockage brut
                try:
                    payment.orbus_raw_response = json.dumps(panier_data, ensure_ascii=False)
                except Exception:  # pragma: no cover
                    payment.orbus_raw_response = str(panier_data)

            # Appliquer le panier au paiement (montant...)
            payment._orbus_infinity_apply_panier(panier_data)

            # Construire et envoyer le payload de paiement
            payload = {
                "montantFacture": panier_data.get("montantFacture") or payment.amount,
                "referencePanier": payment.orbus_infinity_reference_panier,
                "numeroDossier": panier_data.get("numeroDossier", ""),
                "numeroPaiement": payment.name or "",
                "datePaiement": fields.Datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "agentPayeur": payment.env.user.name,
                "bankCode": "BNK-ODOO",
                "payer": True,
                "connaissement": panier_data.get("connaissement", ""),
                "paiementMode": "ODOO",
                "originePaiement": "ODOO",
                "paiementMoyen": "MOBILE_MONEY",
            }

            response = config.api_payer(payload)

            config._create_api_attachment(
                payment,
                "payer",
                "POST",
                f"{config.backendgupe_url}/payer",
                payload,
                response,
            )

            # Stockage de la réponse brute pour analyse technique
            try:
                payment.orbus_raw_response = json.dumps(response, ensure_ascii=False)
            except Exception:  # pragma: no cover
                payment.orbus_raw_response = str(response)

            # Message utilisateur plus lisible pour la bannière
            friendly = False
            if isinstance(response, dict):
                msg = response.get("message") or response.get("Message")
                status_code = response.get("statusCode") or response.get("StatusCode")
                status = response.get("status") or response.get("Status")

                parts = []
                if status_code:
                    parts.append(_("code %s") % status_code)
                if status:
                    parts.append(status)

                suffix = ""
                if parts:
                    suffix = " (%s)" % ", ".join(parts)

                if msg:
                    friendly = _("Paiement Orbus Infinity : %s%s") % (msg, suffix)

            if not friendly:
                friendly = _("Paiement Orbus Infinity effectue." )

            payment.orbus_status_message = friendly

        # Délègue ensuite au comportement Classic / standard
        return super().action_post()

    @api.onchange("orbus_infinity_reference_panier")
    def _onchange_orbus_infinity_reference_panier(self):
        """Lors de la saisie de la référence panier, charger le détail du panier.

        Fonctionnellement similaire à Orbus Classic : on récupère le panier
        Infinity et on pré-remplit le paiement (montant, infos de base),
        tout en conservant la réponse brute.
        """
        for payment in self:
            if not payment.orbus_infinity_reference_panier:
                continue

            if payment.orbus_payment_type != "infinity":
                # On ne tente rien si le paiement n'est pas de type Infinity.
                continue

            try:
                config = payment.env["orbus.infinity.api.config"].get_config_for_company(payment.company_id)

                # Appel detail-panier en priorité avec referencePanier
                panier_data = config.api_detail_panier(
                    referencePanier=payment.orbus_infinity_reference_panier
                )

                if payment.id:
                    config._create_api_attachment(
                        payment,
                        "detail-panier",
                        "GET",
                        f"{config.gateway_url}/detail-panier",
                        {"referencePanier": payment.orbus_infinity_reference_panier},
                        panier_data,
                    )
            except UserError as e:
                # En dev, absence de config/erreur API : on affiche juste le message
                payment.orbus_status_message = str(e)
                continue
            except Exception as e:  # pragma: no cover
                payment.orbus_status_message = str(e)
                continue

            # Stockage dans la même réponse brute que Classic, pour debug
            try:
                payment.orbus_raw_response = json.dumps(panier_data, ensure_ascii=False)
            except Exception:  # pragma: no cover
                payment.orbus_raw_response = str(panier_data)

            payment._orbus_infinity_apply_panier(panier_data)

    def _orbus_infinity_apply_panier(self, panier_data):
        """Applique les données du panier Orbus Infinity sur le paiement.

        À adapter selon la structure réelle de `detail-panier`.
        On essaie au minimum de récupérer un montant.
        """
        # Selon la collection Postman, le montant est dans "montantFacture"
        amount = panier_data.get("montantFacture") or panier_data.get("amount")

        if amount:
            self.amount = amount
            # On laisse Orbus Classic / Infinity partager le même champ de statut
            self.orbus_status_message = _(
                "Panier Orbus Infinity %(ref)s chargé avec succès.",
                ref=self.orbus_infinity_reference_panier,
            )
        else:
            # On n'échoue pas brutalement, on laisse un message générique
            self.orbus_status_message = _(
                "Le mapping du panier Orbus Infinity n'est pas encore configuré. "
                "Vérifiez la méthode _orbus_infinity_apply_panier. Données reçues : %s"
            ) % panier_data

    def action_orbus_infinity_pay(self):
        """Déclenche le paiement via Orbus Infinity.

        Construit un payload minimal et appelle api_payer. À adapter
        dès que la structure exacte sera figée.
        """
        self.ensure_one()

        if self.orbus_payment_type != "infinity":
            raise UserError(
                _("Cette action n'est disponible que pour les paiements Orbus Infinity.")
            )

        if not self.orbus_infinity_reference_panier:
            raise UserError(_("Veuillez renseigner la référence panier Orbus Infinity."))

        config = self.env["orbus.infinity.api.config"].get_config_for_company(self.company_id)

        # On réutilise orbus_raw_response si déjà chargé, sinon on recharge
        panier_data = {}
        if self.orbus_raw_response:
            try:
                panier_data = json.loads(self.orbus_raw_response)
            except Exception:  # pragma: no cover
                panier_data = {}

        if not panier_data:
            panier_data = config.api_detail_panier(
                referencePanier=self.orbus_infinity_reference_panier
            )

        # Construction du payload pour api_payer en suivant la collection Postman
        payload = {
            "montantFacture": panier_data.get("montantFacture") or self.amount,
            "referencePanier": self.orbus_infinity_reference_panier,
            "numeroDossier": panier_data.get("numeroDossier", ""),
            "numeroPaiement": self.name or "",
            "datePaiement": fields.Datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "agentPayeur": self.env.user.name,
            "bankCode": "BNK-ODOO",  # valeur par défaut, à rendre paramétrable si besoin
            "payer": True,
            "connaissement": panier_data.get("connaissement", ""),
            "paiementMode": "ODOO",
            "originePaiement": "ODOO",
            "paiementMoyen": "MOBILE_MONEY",
        }

        # On centralise désormais la logique de paiement dans action_post.
        raise UserError(_("Veuillez utiliser le bouton standard de validation pour les paiements Orbus Infinity."))
