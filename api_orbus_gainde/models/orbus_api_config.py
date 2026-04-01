import logging
from datetime import datetime, timedelta

import requests

from odoo import models, fields, api, _
from odoo.tools import format_date
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class OrbusApiConfig(models.Model):
    """Configuration et client pour l'API Orbus Classic.

    Ce modèle est volontairement générique : il ne contient pas de logique
    métier Odoo, seulement des helpers d'appel API.
    """

    _name = 'orbus.api.config'
    _description = 'Configuration API Orbus Classic'
    _rec_name = 'name'

    name = fields.Char(string="Nom", required=True, default="Orbus Préprod")
    base_url = fields.Char(
        string="URL de base",
        required=True,
        default="https://orbus-preprod.gainde2000.sn:8083/APIORBUSODOO",
        help="URL racine de l'API Orbus (sans le suffixe /api/...).",
    )
    username = fields.Char(string="Utilisateur", required=True, default="odooApp")
    password = fields.Char(string="Mot de passe", required=True, default="odooOrbus2025@@")

    access_token = fields.Char(string="Token d'accès")
    token_expiration = fields.Datetime(string="Expiration du token", readonly=True)

    company_id = fields.Many2one(
        'res.company',
        string="Société",
        required=True,
        default=lambda self: self.env.company,
    )

    batch_periode = fields.Selection(
        selection=[
            ("2017-09", "09/2017"),
            ("2025-03", "03/2025"),
            ("2025-04", "04/2025"),
            ("2025-05", "05/2025"),
        ],
        string="Période batch",
        default="2017-09",
        required=True,
    )

    _sql_constraints = [
        (
            'orbus_config_company_uniq',
            'unique(company_id)',
            "Une seule configuration Orbus est autorisée par société.",
        )
    ]

    # ------------------------------------------------------------------
    # Utils
    # ------------------------------------------------------------------
    @api.model
    def get_config_for_company(self, company=None):
        """Récupère (ou lève) la config pour une société donnée."""
        company = company or self.env.company
        config = self.search([('company_id', '=', company.id)], limit=1)
        if not config:
            raise UserError(_("Aucune configuration Orbus n'est définie pour la société %s.") % company.display_name)
        return config

    # ------------------------------------------------------------------
    # Cron : import batch des factures par période
    # ------------------------------------------------------------------
    @api.model
    def cron_fetch_factures_batch_next_periode(self):
        """Tâche planifiée pour récupérer le prochain batch de factures.

        Pour chaque configuration Orbus (par société) :
        - cherche le dernier batch orbus.facture.batch de la société
        - calcule la période suivante (AAAA-MM)
        - appelle fetch_factures_batch_by_periode sur la config
        """
        configs = self.search([])
        for config in configs:
            company = config.company_id
            last_batch = config.env["orbus.facture.batch"].search(
                [("company_id", "=", company.id)],
                order="periode desc, id desc",
                limit=1,
            )

            # Déterminer la période de départ
            if last_batch and last_batch.periode:
                base_periode = last_batch.periode
            else:
                today = fields.Date.context_today(config)
                base_periode = "%04d-%02d" % (today.year, today.month)

            # Calculer la période suivante AAAA-MM
            try:
                from datetime import datetime as _dt

                dt = _dt.strptime(base_periode + "-01", "%Y-%m-%d")
                year = dt.year
                month = dt.month + 1
                if month > 12:
                    month = 1
                    year += 1
                next_periode = "%04d-%02d" % (year, month)
            except Exception:  # pragma: no cover
                # En cas de format inattendu, on retombe sur la période courante
                today = fields.Date.context_today(config)
                next_periode = "%04d-%02d" % (today.year, today.month)

            try:
                config.fetch_factures_batch_by_periode(next_periode)
            except Exception as e:  # pragma: no cover
                _logger.exception(
                    "[Orbus] Erreur lors de la récupération du batch de factures pour la période %s (société %s): %s",
                    next_periode,
                    company.display_name,
                    e,
                )

    def action_fetch_factures_next_periode(self):
        """Bouton manuel pour déclencher le batch sur la prochaine période.

        Même logique que le cron mais limitée à l'enregistrement courant.
        """
        for config in self:
            company = config.company_id
            last_batch = config.env["orbus.facture.batch"].search(
                [("company_id", "=", company.id)],
                order="periode desc, id desc",
                limit=1,
            )

            if last_batch and last_batch.periode:
                base_periode = last_batch.periode
            else:
                today = fields.Date.context_today(config)
                base_periode = "%04d-%02d" % (today.year, today.month)

            try:
                from datetime import datetime as _dt

                dt = _dt.strptime(base_periode + "-01", "%Y-%m-%d")
                year = dt.year
                month = dt.month + 1
                if month > 12:
                    month = 1
                    year += 1
                next_periode = "%04d-%02d" % (year, month)
            except Exception:  # pragma: no cover
                today = fields.Date.context_today(config)
                next_periode = "%04d-%02d" % (today.year, today.month)

            batch = config.fetch_factures_batch_by_periode(next_periode)
        return True

    def action_fetch_factures_periode_2017_09(self):
        """Bouton manuel pour déclencher le batch pour la période 2017-09.

        Ne dépend pas de la logique de prochaine période.
        """
        for config in self:
            config.fetch_factures_batch_by_periode("2017-09")
        return True

    def action_fetch_factures_selected_periode(self):
        """Bouton manuel pour déclencher le batch sur la période sélectionnée."""
        for config in self:
            if not config.batch_periode:
                raise UserError(_("Veuillez sélectionner une période."))
            config.fetch_factures_batch_by_periode(config.batch_periode)
        return True

    # ------------------------------------------------------------------
    # Authentification
    # ------------------------------------------------------------------
    def _authenticate(self):
        """Appelle POST /api/authentication/login pour obtenir un token.

        Les noms de champs du payload et de la réponse sont à ajuster
        selon la documentation exacte de l'API Orbus.
        """
        self.ensure_one()

        url = f"{self.base_url}/api/authentication/login"
        payload = {
            # À ADAPTER : noms des champs attendus par l'API
            'username': self.username,
            'password': self.password,
        }
        _logger.info("[Orbus] Authentification vers %s", url)

        try:
            resp = requests.post(url, json=payload, timeout=30)
        except Exception as e:  # pragma: no cover - erreur réseau
            raise UserError(_("Erreur réseau lors de l'appel à Orbus : %s") % e) from e

        if resp.status_code != 200:
            raise UserError(_("Erreur login Orbus (%s): %s") % (resp.status_code, resp.text))

        data = resp.json() or {}

        # Adapter aux formats possibles de l'API Orbus
        token = (
            data.get('access_token')
            or data.get('token')
            or (data.get('data') or {}).get('access_token')
            or (data.get('data') or {}).get('token')
        )
        if not token:
            raise UserError(_("Réponse login Orbus sans token: %s") % data)

        self.access_token = token

        expires_in = data.get('expires_in') or (data.get('data') or {}).get('expires_in')
        if expires_in:
            self.token_expiration = fields.Datetime.to_string(
                datetime.utcnow() + timedelta(seconds=expires_in)
            )
        else:
            # Si pas de durée, on considère un token sans expiration gérée côté Odoo
            self.token_expiration = False

    def _get_headers(self):
        """Construit les en-têtes HTTP pour Orbus avec token obligatoire."""
        self.ensure_one()

        # Rafraîchir le token si absent ou expiré
        if not self.access_token or (
            self.token_expiration
            and fields.Datetime.from_string(self.token_expiration) <= fields.Datetime.now()
        ):
            self._authenticate()

        return {
            'Accept': '*/*',
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {self.access_token}",
        }

    # ------------------------------------------------------------------
    # Appels génériques
    # ------------------------------------------------------------------
    def _orbus_get(self, path, params=None):
        self.ensure_one()
        url = f"{self.base_url}{path}"
        _logger.info("[Orbus] GET %s params=%s", url, params)
        
        try:
            headers = self._get_headers()
            resp = requests.get(url, headers=headers, params=params or {}, timeout=30)
        except Exception as e:  # pragma: no cover
            raise UserError(_("Erreur réseau lors de l'appel Orbus GET %s : %s") % (path, e)) from e

        if resp.status_code == 401:
            _logger.warning("[Orbus] Token invalide/expiré, reconnexion...")
            self._authenticate()
            headers = self._get_headers()
            resp = requests.get(url, headers=headers, params=params or {}, timeout=30)

        if resp.status_code != 200:
            raise UserError(_("Appel Orbus GET %s (%s) : %s") % (path, resp.status_code, resp.text))

        return resp.json()

    def _orbus_post(self, path, payload=None):
        self.ensure_one()
        url = f"{self.base_url}{path}"
        _logger.info("[Orbus] POST %s payload=%s", url, payload)

        try:
            headers = self._get_headers()
            resp = requests.post(url, headers=headers, json=payload or {}, timeout=30)
        except Exception as e:  # pragma: no cover
            raise UserError(_("Erreur réseau lors de l'appel Orbus POST %s : %s") % (path, e)) from e

        if resp.status_code == 401:
            _logger.warning("[Orbus] Token invalide/expiré, reconnexion...")
            self._authenticate()
            headers = self._get_headers()
            resp = requests.post(url, headers=headers, json=payload or {}, timeout=30)

        if resp.status_code not in (200, 201):
            raise UserError(_("Appel Orbus POST %s (%s) : %s") % (path, resp.status_code, resp.text))

        # Peut être vide selon l'endpoint
        return resp.json() if resp.content else {}

    # ------------------------------------------------------------------
    # Wrappers métier de base (à spécialiser au besoin)
    # ------------------------------------------------------------------
    def api_get_dossier(self, dossier_id):
        """GET /api/dossiers/GetUnDossier"""
        self.ensure_one()
        params = {'numeroDossier': dossier_id}  # À adapter au nom réel du paramètre
        return self._orbus_get('/api/dossiers/GetUnDossier', params=params)

    def api_get_client(self, client_id):
        """GET /api/clients/GetUnClient"""
        self.ensure_one()
        params = {'numeroClient': client_id}
        return self._orbus_get('/api/clients/GetUnClient', params=params)

    def api_get_facture(self, facture_id):
        """GET /api/factures/GetUneFacture"""
        self.ensure_one()
        params = {'numeroFacture': facture_id}
        return self._orbus_get('/api/factures/GetUneFacture', params=params)

    def api_get_factures_by_periode(self, periode):
        """GET /api/factures/GetFacturesByPeriode

        L'API attend un paramètre "periode" au format AAAA-MM (ex: "2017-09").
        """
        self.ensure_one()
        params = {
            'periode': periode,
        }
        return self._orbus_get('/api/factures/GetFacturesByPeriode', params=params)

    # ------------------------------------------------------------------
    # Création de facture Odoo à partir d'une facture Orbus
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Création de facture Odoo à partir d'une facture Orbus (unitaire)
    # ------------------------------------------------------------------
    def create_odoo_invoice_from_orbus_facture(self, numero_facture):
        """Crée une facture client Odoo à partir d'une facture Orbus.

        Appelle GET /api/factures/GetUneFacture puis mappe la réponse :

        Réponse attendue :
        {
          "statusCode": "200",
          "status": "Success",
          "message": "Liste des factures",
          "data": {
            "numero_facture": "9301/20170801/20170901/ORB",
            "numero_client": 9301,
            "nom_client": "Valdafrique / Laboratoires Cannone",
            "montant_total": 222500,
            "montant_restant_du": 222500,
            "date_echeance": "2017-09-16T00:00:00"
          }
        }

        On crée une facture client (out_invoice) avec une ligne portant le
        produit "Frais de services Orbus" et le montant_total.
        """
        self.ensure_one()

        if not numero_facture:
            raise UserError(_("Veuillez fournir un numéro de facture Orbus."))

        response = self.api_get_facture(numero_facture)
        data = (response or {}).get('data') or {}

        if not data:
            raise UserError(
                _(
                    "La réponse Orbus pour la facture %s ne contient pas de bloc 'data'."
                )
                % numero_facture
            )

        numero_facture_orbus = data.get('numero_facture') or numero_facture
        nom_client = data.get('nom_client')
        numero_client = data.get('numero_client')
        batch_line = self.env["orbus.facture.batch.line"].search(
            [
                ("numero_facture", "=", numero_facture_orbus),
                ("company_id", "=", self.company_id.id),
            ],
            order="id desc",
            limit=1,
        )
        def _to_float(value):
            if value is None:
                return 0.0
            if isinstance(value, str):
                value = value.replace(' ', '').replace(',', '.')
            try:
                return float(value)
            except Exception:
                return 0.0

        def _to_float_or_none(value):
            return _to_float(value) if value is not None else None

        montant_total = _to_float_or_none(data.get('montant_total'))
        montant_ttc = _to_float_or_none(data.get('montant_ttc'))
        if montant_total is None and montant_ttc is not None:
            montant_total = montant_ttc

        montant_tva = _to_float_or_none(data.get('montant_tva'))
        montant_ht = _to_float_or_none(data.get('montant_ht'))
        montant_taxable = _to_float_or_none(data.get('montant_taxable'))
        montant_non_taxable = _to_float_or_none(data.get('montant_non_taxable'))
        montant_exonere = _to_float_or_none(
            data.get('montant_exonore')
            or data.get('montant_exonere')
            or data.get('montant_exoneree')
        )
        if batch_line and (
            batch_line.montant_ttc
            or batch_line.montant_tva
            or batch_line.montant_taxable
            or batch_line.montant_non_taxable
        ):
            montant_ttc = batch_line.montant_ttc or montant_ttc
            montant_total = montant_ttc or montant_total
            montant_tva = batch_line.montant_tva or montant_tva
            montant_taxable = batch_line.montant_taxable or montant_taxable
            montant_non_taxable = batch_line.montant_non_taxable or montant_non_taxable
            if batch_line.montant_ht:
                montant_ht = batch_line.montant_ht
        date_echeance_str = data.get('date_echeance')

        if montant_total is None:
            raise UserError(
                _(
                    "Impossible de déterminer le montant de la facture Orbus %s."
                )
                % numero_facture_orbus
            )

        montant_restant_du = data.get("montant_restant_du")

        # Partenaire : recherche par nom_client, création simple si inexistant.
        if not nom_client:
            nom_client = _("Client Orbus %s") % (data.get('numero_client') or "?")

        tier_account = False
        if numero_client is not None:
            tier_account = f"411G{numero_client}"

        partner = False
        if tier_account:
            partner = self.env['res.partner'].search(
                [('tier_account', '=', tier_account)],
                limit=1,
            )
        if not partner:
            partner = self.env['res.partner'].search(
                [('name', '=', nom_client)],
                limit=1,
            )
        if not partner:
            partner_vals = {
                'name': nom_client,
                'orbus_customer': True,
            }
            if tier_account:
                partner_vals['tier_account'] = tier_account
            partner = self.env['res.partner'].create(partner_vals)

        if montant_taxable is None:
            if montant_ht is not None:
                montant_taxable = montant_ht
            elif montant_tva is not None:
                montant_taxable = montant_tva / 0.18 if montant_tva else 0.0
            else:
                montant_taxable = 0.0

        if montant_tva is None and montant_taxable:
            montant_tva = round(montant_taxable * 0.18, 2)

        if montant_non_taxable is None:
            if montant_exonere is not None:
                montant_non_taxable = montant_exonere
            else:
                if montant_total is None:
                    montant_total = (montant_taxable or 0.0) + (montant_tva or 0.0)
                montant_non_taxable = (montant_total or 0.0) - (montant_taxable or 0.0) - (montant_tva or 0.0)

        montant_taxable = max(montant_taxable, 0.0)
        montant_non_taxable = max(montant_non_taxable, 0.0)

        def _find_account_by_code(code):
            account_model = self.env['account.account']
            domain = [
                ('code', '=', code),
                ('deprecated', '=', False),
            ]
            if 'company_id' in account_model._fields:
                domain.insert(0, ('company_id', '=', self.company_id.id))
            return account_model.search(domain, limit=1)

        taxable_account = _find_account_by_code('706101')
        exempt_account = _find_account_by_code('706102')
        vat_account = _find_account_by_code('443200')
        receivable_account = _find_account_by_code('411100')

        if not taxable_account:
            raise UserError(_("Compte de vente taxable (706101) introuvable."))
        if not exempt_account:
            raise UserError(_("Compte de vente exonérée (706102) introuvable."))
        if not vat_account:
            raise UserError(_("Compte TVA (443200) introuvable."))
        if not receivable_account:
            raise UserError(_("Compte client (411100) introuvable."))

        tax_18 = self.env['account.tax'].search(
            [
                ('type_tax_use', '=', 'sale'),
                ('amount_type', '=', 'percent'),
                ('amount', '=', 18),
                ('company_id', '=', self.company_id.id),
                ('active', '=', True),
            ],
            limit=1,
        )
        if not tax_18:
            tax_18 = self.env['account.tax'].create({
                'name': 'TVA 18% Orbus',
                'amount': 18.0,
                'amount_type': 'percent',
                'type_tax_use': 'sale',
                'company_id': self.company_id.id,
                'invoice_repartition_line_ids': [
                    (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                    (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0, 'account_id': vat_account.id}),
                ],
                'refund_repartition_line_ids': [
                    (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                    (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0, 'account_id': vat_account.id}),
                ],
            })

        product = self.env['product.product'].search(
            [('name', '=', 'Prestation de service Orbus')],
            limit=1,
        )
        if not product:
            product = self.env['product.product'].create({
                'name': 'Prestation de service Orbus',
                'type': 'service',
                'taxes_id': [(6, 0, [tax_18.id])],
            })

        # Date d'échéance : on parse la date si possible.
        invoice_date_due = False
        if date_echeance_str:
            try:
                # Format ISO "YYYY-MM-DDTHH:MM:SS"
                from datetime import datetime as _dt

                invoice_date_due = _dt.fromisoformat(date_echeance_str).date()
            except Exception:  # pragma: no cover
                invoice_date_due = date_echeance_str[:10]

        move_model = self.env['account.move'].with_context(
            default_move_type='out_invoice',
            company_id=self.company_id.id,
        )

        label_date = invoice_date_due or fields.Date.context_today(self)
        label_month_year = format_date(self.env, label_date, date_format="MMMM yyyy")
        line_label = _("Facturation %s") % label_month_year

        line_vals_list = [
            {
                'name': line_label,
                'quantity': 1.0,
                'price_unit': montant_taxable,
                'account_id': taxable_account.id,
                'tax_ids': [(6, 0, [tax_18.id])],
                'product_id': product.id,
            },
            {
                'name': line_label,
                'quantity': 1.0,
                'price_unit': montant_non_taxable,
                'account_id': exempt_account.id,
                'tax_ids': [(6, 0, [])],
                'product_id': product.id,
            },
        ]
        move_vals = {
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_origin': numero_facture_orbus,
            'ref': _("Facturation %s") % label_month_year,
            'invoice_line_ids': [(0, 0, vals) for vals in line_vals_list],
            'company_id': self.company_id.id,
        }
        if invoice_date_due:
            move_vals['invoice_date_due'] = invoice_date_due

        invoice = move_model.create(move_vals)

        # Forcer le mapping des comptes après création (fiscal position peut écraser)
        taxable_lines = invoice.invoice_line_ids.filtered(
            lambda line: tax_18 in line.tax_ids
        )
        exempt_lines = invoice.invoice_line_ids.filtered(
            lambda line: not line.tax_ids
        )

        if taxable_lines:
            taxable_lines.write({
                'account_id': taxable_account.id,
                'tax_ids': [(6, 0, [tax_18.id])],
            })
        if exempt_lines:
            exempt_lines.write({
                'account_id': exempt_account.id,
                'tax_ids': [(6, 0, [])],
            })

        receivable_line = invoice.line_ids.filtered(
            lambda line: line.account_id.account_type == 'asset_receivable'
        )[:1]
        if receivable_line and receivable_line.account_id != receivable_account:
            receivable_line.write({'account_id': receivable_account.id})

        # Paiement automatique si la réponse Orbus indique un règlement total/partiel
        # if montant_restant_du is not None:
        #     try:
        #         amount_paid = float(montant_total) - float(montant_restant_du)
        #     except Exception:  # pragma: no cover
        #         amount_paid = 0.0

        #     if amount_paid > 0:
        #         # La facture doit être postée avant l'enregistrement d'un paiement
        #         invoice.action_post()
        #         currency = invoice.currency_id or self.company_id.currency_id
        #         amount_paid = currency.round(amount_paid)
        #         amount_paid = min(amount_paid, invoice.amount_residual)
        #         if amount_paid > 0:
        #             self._register_payment_for_invoice(invoice, amount_paid)

        return invoice

    def _register_payment_for_invoice(self, invoice, amount):
        """Crée un paiement client pour une facture donnée."""
        self.ensure_one()

        if not invoice or amount <= 0:
            return False

        journal = self.env["account.journal"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("type", "in", ("bank", "cash")),
                ("active", "=", True),
            ],
            limit=1,
        )
        if not journal:
            raise UserError(_("Aucun journal de type banque ou caisse n'est configuré."))

        register_model = self.env["account.payment.register"].with_context(
            active_model="account.move",
            active_ids=invoice.ids,
        )

        vals = {
            "amount": amount,
            "payment_date": fields.Date.context_today(self),
            "journal_id": journal.id,
        }

        if "payment_method_line_id" in register_model._fields:
            method_line = journal.inbound_payment_method_line_ids[:1]
            if not method_line:
                raise UserError(_("Aucune méthode de paiement entrante n'est configurée sur le journal %s.") % journal.display_name)
            vals["payment_method_line_id"] = method_line.id
        elif "payment_method_id" in register_model._fields:
            method = journal.inbound_payment_method_ids[:1]
            if not method:
                raise UserError(_("Aucune méthode de paiement entrante n'est configurée sur le journal %s.") % journal.display_name)
            vals["payment_method_id"] = method.id

        payment_register = register_model.create(vals)
        payment_register.action_create_payments()
        return True

    # ------------------------------------------------------------------
    # Batch de factures par periode (sans creation automatique de factures)
    # ------------------------------------------------------------------
    def fetch_factures_batch_by_periode(self, periode):
        """Cree un lot orbus.facture.batch a partir d'une periode Orbus.

        - appelle GET /api/factures/GetFacturesByPeriode?periode=AAAA-MM
        - enregistre les metadonnees du batch (periode, params, statut)
        - enregistre chaque facture retournee en lignes orbus.facture.batch.line
        """
        self.ensure_one()

        if not periode:
            raise UserError(_("Veuillez fournir une periode au format AAAA-MM."))

        response = self.api_get_factures_by_periode(periode)
        data = (response or {}).get("data") or {}
        factures = data.get("factures") or []
        periode_resp = data.get("periode") or periode

        import json as _json

        params = {"periode": periode}

        batch_vals = {
            "name": _("Batch factures Orbus %s") % periode_resp,
            "code": "%s" % periode_resp,
            "periode": periode_resp,
            "params_json": _json.dumps(params, ensure_ascii=False),
            "status_code": response.get("statusCode") if isinstance(response, dict) else False,
            "status": response.get("status") if isinstance(response, dict) else False,
            "message": response.get("message") if isinstance(response, dict) else False,
            "company_id": self.company_id.id,
        }

        batch = self.env["orbus.facture.batch"].create(batch_vals)

        line_model = self.env["orbus.facture.batch.line"]
        line_vals_list = []
        tva_rate = 0.18
        for f in factures:
            montant_ttc = f.get("montant_ttc") or 0.0
            montant_du = f.get("montant_du")
            if montant_du is None:
                montant_du = f.get("montant_restant_du")
            montant_tva = f.get("montant_tva")

            # Valeurs par défaut pour éviter les variables non définies
            tva_declaree = 0.0
            ht_calcule = 0.0
            montant_taxable = 0.0
            montant_non_taxable = 0.0
            montant_exonere = 0.0

            # Règle demandée :
            # montant_ttc = montant_ht + montant_exonore + montant_tva
            # On reçoit uniquement montant_ttc et montant_tva.
            tva_declaree = float(montant_tva or 0.0)
            ht_calcule = tva_declaree / tva_rate if tva_declaree else 0.0
            montant_exonere = montant_ttc - ht_calcule - tva_declaree

            montant_taxable = max(ht_calcule, 0.0)
            montant_non_taxable = montant_exonere

            # Données manquantes côté batch : on simule le montant dû si absent.
            if montant_du is None:
                montant_du = montant_ttc

            line_vals_list.append(
                {
                    "batch_id": batch.id,
                    "numero_facture": f.get("numero_facture"),
                    "numero_client": str(f.get("numero_client")) if f.get("numero_client") is not None else False,
                    "nom_client": f.get("nom_client"),
                    "montant_ttc": montant_ttc,
                    "montant_tva": tva_declaree,
                    "montant_ht": ht_calcule,
                    "montant_du": montant_du,
                    "montant_taxe_18": tva_declaree,
                    "montant_taxable": montant_taxable,
                    "montant_non_taxable": montant_non_taxable,
                    "devise": f.get("devise"),
                }
            )

        if line_vals_list:
            line_model.create(line_vals_list)

        return batch
