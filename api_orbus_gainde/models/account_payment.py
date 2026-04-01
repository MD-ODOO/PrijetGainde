import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    orbus_payment_type = fields.Selection(
        selection=[
            ("classic", "Orbus Classic"),
            ("infinity", "Orbus Infinity"),
            ("odoo_only", "Paiement Odoo uniquement"),
        ],
        string="Type de paiement Orbus",
        help="Type de paiement Orbus utilisé pour cette écriture.",
    )

    orbus_dossier_number = fields.Char(
        string="Numéro dossier Orbus",
        help="Numéro de dossier Orbus saisi par le caissier.",
    )

    orbus_raw_response = fields.Text(
        string="Réponse Orbus (brute)",
        readonly=True,
        help="Contenu brut renvoyé par l'API Orbus pour ce dossier.",
    )

    orbus_status_message = fields.Text(
        string="Information Orbus",
        readonly=True,
        help="Message d'information suite au chargement du dossier Orbus.",
    )

    orbus_invoice_id = fields.Many2one(
        "account.move",
        string="Facture Orbus",
        readonly=True,
        copy=False,
        help="Facture client créée automatiquement à partir du dossier Orbus.",
    )

    @api.onchange("orbus_payment_type")
    def _onchange_orbus_payment_type(self):
        """Tous les paiements Orbus sont des paiements client (recevoir).

        Lorsqu'un type Orbus est sélectionné, on force le type de paiement
        et le type de partenaire pour rester cohérent.
        """
        for payment in self:
            if payment.orbus_payment_type:
                payment.payment_type = "inbound"
                payment.partner_type = "customer"

    def action_post(self):
        """Surcharge du post Odoo pour brancher Orbus Classic.

        - Si le paiement est de type Orbus Classic, on appelle d'abord
          l'API Classic (_orbus_classic_call_payment_api), puis on laisse
          Odoo poster normalement.
        - Sinon, on délègue au comportement standard / autres modules.
        """
        classic_payments = self.filtered(lambda p: p.orbus_payment_type == "classic")
        other_payments = self - classic_payments

        # Pour les paiements Classic : appel API avant le post
        for payment in classic_payments:
            if not payment.orbus_dossier_number:
                raise UserError(_("Veuillez renseigner le numéro de dossier Orbus."))

            config = payment.env["orbus.api.config"].get_config_for_company(payment.company_id)

            dossier_data = {}
            if payment.orbus_raw_response:
                try:
                    dossier_data = json.loads(payment.orbus_raw_response)
                except Exception:  # pragma: no cover
                    dossier_data = {}

            if not dossier_data:
                dossier_data = config.api_get_dossier(payment.orbus_dossier_number)

                # Stockage de la réponse brute
                try:
                    payment.orbus_raw_response = json.dumps(dossier_data, ensure_ascii=False)
                except Exception:  # pragma: no cover
                    payment.orbus_raw_response = str(dossier_data)

                # Application éventuelle au paiement (montant, partenaire...)
                payment._orbus_classic_apply_dossier(dossier_data)

            # Appel de l'API de paiement Orbus Classic avant le post Odoo
            response = payment._orbus_classic_call_payment_api(config, dossier_data)

            message = False
            if isinstance(response, dict):
                message = response.get("message") or response.get("Message")
            if not message:
                message = _(
                    "Paiement Orbus Classic effectué pour le dossier %(dossier)s.",
                    dossier=payment.orbus_dossier_number,
                )
            payment.orbus_status_message = message

        # On laisse ensuite Odoo poster normalement tous les paiements
        return super().action_post()

    @api.onchange("orbus_dossier_number")
    def _onchange_orbus_dossier_number(self):
        """Lors de la saisie du numéro de dossier Orbus, charger le dossier.

        Pour les paiements de type "Orbus Classic", on appelle l'API Orbus
        afin de pré-remplir le montant, le partenaire et de conserver la
        réponse brute dans orbus_raw_response.
        """
        for payment in self:
            # Si le numéro est vidé, on nettoie les infos Orbus
            if not payment.orbus_dossier_number:
                payment.orbus_raw_response = False
                payment.orbus_status_message = False
                continue

            if (
                payment.orbus_payment_type == "classic"
                and payment.orbus_dossier_number
            ):
                # Message immédiat pour voir que l'onchange est bien déclenché
                payment.orbus_status_message = _(
                    "Recherche du dossier Orbus %(dossier)s...",
                    dossier=payment.orbus_dossier_number,
                )

                try:
                    config = (
                        payment.env["orbus.api.config"].get_config_for_company(payment.company_id)
                    )
                    dossier_data = config.api_get_dossier(payment.orbus_dossier_number)
                except UserError as e:
                    # En dev, absence de config/token : on affiche juste le message, sans bloquer l'enregistrement
                    payment.orbus_status_message = str(e)
                    continue
                except Exception as e:  # pragma: no cover
                    payment.orbus_status_message = str(e)
                    continue

                # Stockage de la réponse brute pour faciliter le débogage / l'analyse
                try:
                    payment.orbus_raw_response = json.dumps(dossier_data, ensure_ascii=False)
                except Exception:  # pragma: no cover - sécurité en cas de données non sérialisables
                    payment.orbus_raw_response = str(dossier_data)

                payment._orbus_classic_apply_dossier(dossier_data)

                payment.orbus_status_message = _(
                    "Dossier Orbus %(dossier)s chargé avec succès.",
                    dossier=payment.orbus_dossier_number,
                )
        # Pas de toast depuis onchange (Odoo ne traite pas les actions ici).
        # Le champ orbus_status_message dans la vue permet déjà un retour utilisateur.

    def action_orbus_classic_fetch(self):
        """Récupère les infos du dossier Orbus Classic et prépare le paiement.

        - Vérifie que le paiement est de type Orbus Classic.
        - Appelle l'API Orbus pour charger le dossier.
        - Stocke la réponse brute puis délègue le mapping métier
          à _orbus_classic_apply_dossier().
        """
        self.ensure_one()
        if self.orbus_payment_type != "classic":
            raise UserError(
                _("Cette action n'est disponible que pour les paiements Orbus Classic.")
            )
        if not self.orbus_dossier_number:
            raise UserError(_("Veuillez renseigner le numéro de dossier Orbus."))

        config = (
            self.env["orbus.api.config"].get_config_for_company(self.company_id)
        )
        dossier_data = config.api_get_dossier(self.orbus_dossier_number)

        # Stockage de la réponse brute pour faciliter le débogage / l'analyse
        try:
            self.orbus_raw_response = json.dumps(dossier_data, ensure_ascii=False)
        except Exception:  # pragma: no cover - sécurité en cas de données non sérialisables
            self.orbus_raw_response = str(dossier_data)

        self._orbus_classic_apply_dossier(dossier_data)

        # Message d'information stocké dans le champ dédié, affiché en bannière dans la vue
        self.orbus_status_message = _(
            "Dossier Orbus %(dossier)s chargé avec succès.",
            dossier=self.orbus_dossier_number,
        )

        # Pas de popup/toast : on reste sur le formulaire
        return True

    def _orbus_classic_apply_dossier(self, dossier_data):
        """Applique les données du dossier Orbus sur le paiement courant.

        Attendu côté API "GetUnDossier" (réponse réelle) :
        {
            "statusCode": "200",
            "status": "Success",
            "message": "Dossier récupéré avec succès",
            "data": {
                "numero_dossier": 2720285,
                "numero_client": 0,
                "montant_ttc": 17000,
                "montant_a_payer": 17000,
                "description": "Ouverture dossier CF ponctuel",
                "taxes": [],
                "statut_dossier": null
            }
        }

        - le montant à utiliser vient de data["montant_a_payer"] (fallback sur
          data["montant_ttc"])
        - l'identification du client peut se faire via numero_client si
          nécessaire, mais le nom lisible n'est pas fourni par cette réponse.

        1) met à jour le montant sur le paiement
        2) si possible, met à jour/ crée un partenaire
        3) crée une facture client liée si aucune facture Orbus n'existe encore
        """
        # On récupère le bloc "data" qui contient les infos métier.
        data = (dossier_data or {}).get("data") or {}

        if not data:
            raise UserError(
                _(
                    "La réponse Orbus ne contient pas de bloc 'data'.\n\n"
                    "Exemple de données reçues : %s"
                )
                % dossier_data
            )

        # Montant : priorité au montant à payer, puis au montant TTC.
        amount = data.get("montant_a_payer")
        if amount is None:
            amount = data.get("montant_ttc")

        if amount is None:
            raise UserError(
                _(
                    "Impossible de déterminer le montant à partir du dossier Orbus. "
                    "Les champs 'montant_a_payer' ou 'montant_ttc' sont absents.\n\n"
                    "Exemple de données reçues : %s"
                )
                % dossier_data
            )

        # Tentative de construction d'un nom de client lisible.
        client_name = dossier_data.get("customer") or dossier_data.get("client_name")
        if not client_name:
            numero_client = data.get("numero_client")
            if numero_client:
                client_name = _("Client Orbus %s") % numero_client

        partner = False
        if client_name:
            # Recherche ou création simple du partenaire à partir du nom.
            partner = self.env["res.partner"].search(
                [
                    ("name", "=", client_name),
                ],
                limit=1,
            )
            if not partner:
                partner = self.env["res.partner"].create({"name": client_name})

        # Application au paiement : montant toujours, partenaire seulement si trouvé.
        if partner:
            self.partner_id = partner.id
        self.amount = amount

        # Création automatique d'une facture client liée si nécessaire.
        # On ne crée qu'une seule facture par paiement et seulement si on a un partenaire.
        if not self.orbus_invoice_id and (self.partner_id or partner):
            partner_for_invoice = partner or self.partner_id
            move_model = self.env["account.move"].with_context(default_move_type="out_invoice")

            # Compte de revenu par défaut : premier compte "income" de la société
            income_account = self.env["account.account"].search(
                [
                    ("company_id", "=", self.company_id.id),
                    ("internal_group", "=", "income"),
                    ("deprecated", "=", False),
                ],
                limit=1,
            )

            line_vals = {
                "name": _("Dossier Orbus %s") % (self.orbus_dossier_number or ""),
                "quantity": 1.0,
                "price_unit": amount,
            }
            if income_account:
                line_vals["account_id"] = income_account.id

            move_vals = {
                "move_type": "out_invoice",
                "partner_id": partner_for_invoice.id,
                "invoice_origin": self.orbus_dossier_number or "",
                "invoice_line_ids": [(0, 0, line_vals)],
                "company_id": self.company_id.id,
            }

            invoice = move_model.create(move_vals)
            self.orbus_invoice_id = invoice.id

    def action_orbus_classic_pay(self):
        """Déclenche le paiement via Orbus Classic puis valide le paiement Odoo.

        La logique d'appel POST à l'API Orbus doit être implémentée dans
        _orbus_classic_call_payment_api(). Cette méthode :

        - Vérifie le type Orbus Classic.
        - Appelle l'API externe (hook).
        - Poste le paiement dans Odoo.
        - Ouvre le paiement dans une fenêtre dédiée pour impression du reçu.
        """
        self.ensure_one()
        if self.orbus_payment_type != "classic":
            raise UserError(
                _("Cette action n'est disponible que pour les paiements Orbus Classic.")
            )
        if not self.orbus_dossier_number:
            raise UserError(_("Veuillez renseigner le numéro de dossier Orbus."))

        config = (
            self.env["orbus.api.config"].get_config_for_company(self.company_id)
        )

        dossier_data = {}
        if self.orbus_raw_response:
            try:
                dossier_data = json.loads(self.orbus_raw_response)
            except Exception:  # pragma: no cover
                dossier_data = {}

        self._orbus_classic_call_payment_api(config, dossier_data)

        # Si l'appel externe est ok, on poste le paiement dans Odoo.
        self.action_post()

        # Ouvre le paiement dans une nouvelle fenêtre pour permettre l'impression du reçu.
        return {
            "name": _("Reçu de paiement"),
            "type": "ir.actions.act_window",
            "res_model": "account.payment",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
            "context": dict(self.env.context),
        }

    def _orbus_classic_call_payment_api(self, config, dossier_data):
        """Hook pour appeler l'API Orbus Classic en POST.

        End-point fourni :
        POST /api/dossiers/PaymentDossierCF
        Payload attendu (JSON) :
        {
          "numero_dossier": ...,      # numéro du dossier Orbus
          "payment_reference": ...,   # référence de paiement Odoo
          "date_payment": ...,        # date du paiement
          "montant": ...,             # montant réglé
          "montant_timbre": ...,      # montant de timbre (si applicable)
          "numero_cheque": ...,       # n° de chèque le cas échéant
          "ordre_virement": ...,      # ordre de virement le cas échéant
          "caissier": ...,            # nom de l'utilisateur connecté
          "mode_paiement": ...        # mode de paiement (Odoo -> Orbus)
        }

        Cette méthode construit le payload à partir du paiement Odoo et du
        dossier Orbus, envoie la requête via config._orbus_post() et renvoie
        la réponse JSON (dict).
        """
        self.ensure_one()
        config.ensure_one()

        data = (dossier_data or {}).get("data") or {}

        numero_dossier = data.get("numero_dossier") or self.orbus_dossier_number

        # Référence de paiement : on privilégie name, puis ref.
        payment_reference = self.name or getattr(self, "ref", False) or self.orbus_dossier_number

        # Date de paiement : date du paiement Odoo.
        date_payment = self.date or fields.Date.context_today(self)

        # Montant : montant du paiement dans Odoo (déjà calé sur le dossier).
        montant = self.amount or data.get("montant_a_payer") or data.get("montant_ttc")

        # Champs optionnels (cheque, virement, timbre) : à spécialiser au besoin.
        montant_timbre = 0.0
        numero_cheque = getattr(self, "check_number", False) or None
        ordre_virement = None

        # Caissier : nom de l'utilisateur connecté.
        caissier = self.env.user.name

        # Mode de paiement : on mappe les infos Odoo vers les codes Orbus.
        # - CHK : chèque
        # - VIR : virement
        # - ESP : espèces (valeur par défaut)
        mode_paiement = "ESP"

        payment_method_line = getattr(self, "payment_method_line_id", False)
        pm_code = ""
        pm_name = ""
        if payment_method_line and getattr(payment_method_line, "payment_method_id", False):
            pm_code = (payment_method_line.payment_method_id.code or "").lower()
            pm_name = (payment_method_line.payment_method_id.name or "").lower()

        journal = self.journal_id
        journal_name = (journal.name or "").lower() if journal else ""
        journal_type = journal.type if journal else ""

        # Détection du chèque
        if (
            "cheque" in pm_name
            or "chèque" in pm_name
            or pm_code in ("check", "cheque", "chk")
            or "cheque" in journal_name
            or "chèque" in journal_name
        ):
            mode_paiement = "CHK"
        # Détection du virement
        elif (
            "virement" in pm_name
            or pm_code == "vir"
            or "vir " in pm_name
            or journal_type == "bank"
            or "virement" in journal_name
        ):
            mode_paiement = "VIR"
        # Sinon on garde ESP (caisse / espèces)
        elif journal_type == "cash" or "esp" in journal_name:
            mode_paiement = "ESP"

        payload = {
            "numero_dossier": numero_dossier,
            "payment_reference": payment_reference,
            "date_payment": str(date_payment) if date_payment else None,
            "montant": montant,
            "montant_timbre": montant_timbre,
            "numero_cheque": numero_cheque,
            "ordre_virement": ordre_virement,
            "caissier": caissier,
            "mode_paiement": mode_paiement,
        }

        # Appel POST vers l'endpoint Orbus Classic.
        response = config._orbus_post("/api/dossiers/PaymentDossierCF", payload=payload)

        # On conserve la dernière réponse brute dans orbus_raw_response pour
        # faciliter le débogage.
        try:
            self.orbus_raw_response = json.dumps(response or {}, ensure_ascii=False)
        except Exception:  # pragma: no cover
            self.orbus_raw_response = str(response)

        return response or {}
