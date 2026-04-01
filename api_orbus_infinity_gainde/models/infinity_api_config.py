import base64
import json
import logging
import os
import re
import unicodedata
from datetime import datetime, timedelta

import requests

from odoo import models, fields, api, _
from odoo.modules.module import get_module_resource
from odoo.tools import format_date
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class OrbusInfinityApiConfig(models.Model):
    """Configuration + client pour Orbus Infinity (GUPE).

    Basé sur la collection Postman `integration-odoo` :
    - Token : POST https://auth-gupe.gainde2000.sn/realms/gupe-realm/protocol/openid-connect/token
    - List panier : GET https://gupe.gainde2000.sn/backendgateway/integration-odoo/list-panier
    - Détail panier : GET https://gupe.gainde2000.sn/backendgateway/integration-odoo/detail-panier
    - Paiement : POST https://api-gupe.gainde2000.sn/backendgupe/odoo/payer
    """

    _name = 'orbus.infinity.api.config'
    _description = 'Configuration API Orbus Infinity / GUPE'
    _rec_name = 'name'

    name = fields.Char(string="Nom", required=True, default="Orbus Infinity")

    # URLs techniques
    auth_url = fields.Char(
        string="URL Token",
        required=True,
        default="https://auth-gupe.gainde2000.sn/realms/gupe-realm/protocol/openid-connect/token",
    )
    gateway_url = fields.Char(
        string="URL passerelle backend",
        required=True,
        default="https://gupe.gainde2000.sn/backendgateway/integration-odoo",
        help="Racine des endpoints liste/detail panier.",
    )
    backendgupe_url = fields.Char(
        string="URL du backend GUPE",
        required=True,
        default="https://api-gupe.gainde2000.sn/backendgupe/odoo",
        help="Racine des endpoints de paiement (odoo/payer).",
    )

    verify_ssl = fields.Boolean(
        string="Vérifier SSL",
        default=True,
        help="Désactiver uniquement si le certificat du serveur n'est pas reconnu.",
    )
    ca_cert_path = fields.Char(
        string="Chemin CA",
        help="Chemin vers un bundle CA (ex: /etc/ssl/certs/ca-certificates.crt).",
    )

    # Credentials Keycloak
    client_id = fields.Char(string="ID client", required=True, default="gupe")
    username = fields.Char(string="Utilisateur", required=True, default="odoo")
    password = fields.Char(string="Mot de passe", required=True)
    grant_type = fields.Char(string="Type de grant", required=True, default="password")

    access_token = fields.Char(string="Token d'accès", readonly=True)
    token_expiration = fields.Datetime(string="Expiration du token", readonly=True)

    company_id = fields.Many2one(
        'res.company',
        string="Société",
        required=True,
        default=lambda self: self.env.company,
    )

    _sql_constraints = [
        (
            'orbus_infinity_config_company_uniq',
            'unique(company_id)',
            "Une seule configuration Orbus Infinity est autorisée par société.",
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
            raise UserError(_("Aucune configuration Orbus Infinity n'est définie pour la société %s.") % company.display_name)
        return config

    # ------------------------------------------------------------------
    # Authentification (Keycloak password grant)
    # ------------------------------------------------------------------
    def _authenticate(self):
        self.ensure_one()

        data = {
            'username': self.username,
            'password': self.password,
            'grant_type': self.grant_type,
            'client_id': self.client_id,
        }
        _logger.info("[OrbusInfinity] Auth vers %s", self.auth_url)

        verify = self.ca_cert_path or self.verify_ssl
        try:
            resp = requests.post(self.auth_url, data=data, timeout=30, verify=verify)
        except Exception as e:  # pragma: no cover
            raise UserError(_("Erreur réseau lors de l'appel token Orbus Infinity : %s") % e) from e

        if resp.status_code != 200:
            raise UserError(_("Erreur token Orbus Infinity (%s): %s") % (resp.status_code, resp.text))

        payload = resp.json() or {}
        token = payload.get('access_token')
        if not token:
            raise UserError(_("Réponse token Orbus Infinity sans access_token : %s") % payload)

        self.access_token = token
        expires_in = payload.get('expires_in')
        if expires_in:
            self.token_expiration = fields.Datetime.to_string(
                datetime.utcnow() + timedelta(seconds=expires_in)
            )
        else:
            self.token_expiration = False

    def _get_headers(self):
        self.ensure_one()
        # Toujours rafraîchir le token avant chaque requête (exigence API).
        self._authenticate()

        return {
            'Authorization': f"Bearer {self.access_token}",
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    # ------------------------------------------------------------------
    # Helpers HTTP
    # ------------------------------------------------------------------
    def _create_api_attachment(self, record, api_name, method, url, request_data, response_data):
        if not record or not record.id:
            return False

        payload = {
            "api": api_name,
            "method": method,
            "url": url,
            "request": request_data,
            "response": response_data,
            "timestamp": fields.Datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        content = json.dumps(payload, ensure_ascii=False, indent=2)
        filename = "%s_%s.json" % (
            api_name.replace("/", "-"),
            fields.Datetime.now().strftime("%Y%m%d_%H%M%S"),
        )

        self.env["ir.attachment"].create(
            {
                "name": filename,
                "res_model": record._name,
                "res_id": record.id,
                "type": "binary",
                "datas": base64.b64encode(content.encode("utf-8")),
                "mimetype": "application/json",
            }
        )
        return True

    def _get_gateway(self, endpoint, params=None):
        self.ensure_one()
        headers = self._get_headers()
        url = f"{self.gateway_url}/{endpoint.lstrip('/')}"
        _logger.info("[OrbusInfinity] GET %s params=%s", url, params)
        verify = self.ca_cert_path or self.verify_ssl
        try:
            resp = requests.get(url, headers=headers, params=params or {}, timeout=30, verify=verify)
        except Exception as e:  # pragma: no cover
            raise UserError(_("Erreur réseau lors de l'appel Orbus Infinity GET %s : %s") % (url, e)) from e
        if resp.status_code != 200:
            raise UserError(_("Appel Orbus Infinity GET %s (%s) : %s") % (url, resp.status_code, resp.text))
        return resp.json()

    def _post_backend(self, endpoint, payload=None):
        self.ensure_one()
        headers = self._get_headers()
        url = f"{self.backendgupe_url}/{endpoint.lstrip('/')}"
        _logger.info("[OrbusInfinity] POST %s payload=%s", url, payload)
        verify = self.ca_cert_path or self.verify_ssl
        try:
            resp = requests.post(url, headers=headers, json=payload or {}, timeout=30, verify=verify)
        except Exception as e:  # pragma: no cover
            raise UserError(_("Erreur réseau lors de l'appel Orbus Infinity POST %s : %s") % (url, e)) from e
        if resp.status_code not in (200, 201):
            raise UserError(_("Appel Orbus Infinity POST %s (%s) : %s") % (url, resp.status_code, resp.text))
        return resp.json() if resp.content else {}

    # ------------------------------------------------------------------
    # Wrappers métiers (paniers & paiement)
    # ------------------------------------------------------------------
    def api_list_paniers(self, **filters):
        """GET list-panier avec filtres optionnels.

        Filtres possibles selon Postman :
        - connaissement, numeroDossier, referencePanier, numeroPaiement,
          transitaire, dateGenerateReference, lastFetchedDate,
          startDatePaiement, endDatePaiement, payer.
        """
        self.ensure_one()
        # IMPORTANT: certains backends interprètent un paramètre vide (ex: payer="")
        # comme un filtre actif. Pour éviter de récupérer uniquement les paniers payés
        # par défaut, on NE transmet pas les paramètres vides.
        effective_filters = {
            k: v for k, v in (filters or {}).items() if v not in (None, "", False)
        }
        return self._get_gateway("list-panier", params=effective_filters)

    def api_detail_panier(self, **filters):
        """GET detail-panier.

        Souvent appelé au moins avec referencePanier.
        """
        self.ensure_one()
        params = {k: v for k, v in filters.items() if v not in (None, "")}
        if not params.get('referencePanier'):
            raise UserError(_("`referencePanier` est requis pour detail-panier."))
        return self._get_gateway('detail-panier', params=params)

    def api_payer(self, payload):
        """POST odoo/payer.

        Le payload doit suivre la structure de la collection Postman, par ex. :
        {
            'montantFacture': 35400.0,
            'referencePanier': '...',
            'numeroDossier': '...',
            'numeroPaiement': '...',
            'datePaiement': 'YYYY-MM-DD HH:MM:SS',
            'agentPayeur': 'Nom Prénom',
            'bankCode': 'BNK-ODOO',
            'payer': True,
            'connaissement': '...',
            'paiementMode': 'ODOO',
            'originePaiement': 'ODOO',
            'paiementMoyen': 'MOBILE_MONEY',
        }
        """
        self.ensure_one()
        if not isinstance(payload, dict):
            raise UserError(_("Le payload de api_payer doit être un dictionnaire."))
        return self._post_backend('payer', payload=payload)

    # ------------------------------------------------------------------
    # Batch paniers (list-panier) + création factures
    # ------------------------------------------------------------------
    def _normalize_list_panier_response(self, response):
        content = []
        meta = {}

        if isinstance(response, dict):
            data_block = response.get("data") or {}
            meta = {
                "status_code": (
                    response.get("statusCode")
                    or response.get("StatusCode")
                    or data_block.get("statusCode")
                    or data_block.get("StatusCode")
                ),
                "status": (
                    response.get("status")
                    or response.get("Status")
                    or data_block.get("status")
                    or data_block.get("Status")
                ),
                "message": (
                    response.get("message")
                    or response.get("Message")
                    or data_block.get("message")
                    or data_block.get("Message")
                ),
                "total_elements": (
                    response.get("totalElements")
                    or response.get("total_elements")
                    or data_block.get("totalElements")
                    or data_block.get("total_elements")
                ),
                "total_pages": (
                    response.get("totalPages")
                    or response.get("total_pages")
                    or data_block.get("totalPages")
                    or data_block.get("total_pages")
                ),
                "page_size": (
                    response.get("size")
                    or response.get("pageSize")
                    or response.get("page_size")
                    or data_block.get("size")
                    or data_block.get("pageSize")
                    or data_block.get("page_size")
                ),
                "page_number": (
                    response.get("number")
                    or response.get("page")
                    or response.get("pageNumber")
                    or response.get("page_number")
                    or data_block.get("number")
                    or data_block.get("page")
                    or data_block.get("pageNumber")
                    or data_block.get("page_number")
                ),
            }
            content = (
                response.get("content")
                or response.get("data")
                or data_block.get("content")
                or data_block.get("data")
                or response.get("paniers")
                or response.get("panier")
                or []
            )
            if isinstance(content, dict) and content.get("content"):
                content = content.get("content")
        elif isinstance(response, list):
            content = response

        if not isinstance(content, list):
            content = []

        return content, meta

    def _compute_amounts_for_destination(self, montant_ttc, destination):
        # NOTE: L'API Orbus a changé : `destination` contient maintenant un pays
        # (ex: "Sénégal") au lieu de "IMPORT/EXPORT/TRANSIT".
        # Règle demandée : si le pays = Sénégal (avec ou sans accent) => TVA 18%.
        # On garde la compatibilité avec l'ancien format où destination == "IMPORT".
        # `destination` peut arriver sous forme de chaîne ou d'objet (dict) selon l'API.
        destination_value = destination
        if isinstance(destination_value, dict):
            # Priorité aux clés les plus probables.
            destination_value = (
                destination_value.get("name")
                or destination_value.get("country")
                or destination_value.get("country_name")
                or destination_value.get("libelle")
                or destination_value.get("label")
                or destination_value.get("value")
                or destination_value.get("code")
                or ""
            )
        destination_raw = (destination_value or "").strip()

        def _norm(value):
            value = (value or "").strip()
            value = unicodedata.normalize("NFKD", value)
            value = "".join(ch for ch in value if not unicodedata.combining(ch))
            value = value.lower()
            return " ".join(value.split())

        destination_norm = _norm(destination_raw)
        if destination_norm in ("n/a", "na", "none", "null"):
            destination_norm = ""

        def _is_senegal(value_norm: str) -> bool:
            if not value_norm:
                return False
            # Nettoyage de ponctuation puis tokenization.
            cleaned = re.sub(r"[^a-z0-9]+", " ", value_norm)
            tokens = {t for t in cleaned.split() if t}
            # ISO alpha-2 attendu possible: SN
            if tokens == {"sn"}:
                return True
            if "senegal" in tokens:
                return True
            # Variantes fréquentes (après normalisation accents)
            if {"republique", "du", "senegal"}.issubset(tokens):
                return True
            return False

        apply_vat_18 = False
        if destination_norm == "import":
            apply_vat_18 = True
        elif _is_senegal(destination_norm):
            apply_vat_18 = True
        tva_rate = 0.18

        currency = self.company_id.currency_id

        montant_ttc = montant_ttc or 0.0
        if apply_vat_18:
            # Montant TTC incluant TVA : ventiler en HT + TVA
            montant_ht = montant_ttc / (1 + tva_rate) if tva_rate else montant_ttc
            montant_tva = montant_ttc - montant_ht
        else:
            montant_ht = montant_ttc
            montant_tva = 0.0

        if currency:
            montant_ht = currency.round(montant_ht)
            montant_tva = currency.round(montant_tva)

        return montant_ht, montant_tva, apply_vat_18

    def fetch_paniers_batch(self, filters=None):
        """Crée un batch à partir de list-panier avec les filtres fournis."""
        self.ensure_one()

        filters = filters or {}
        # Ne pas conserver les filtres vides : sinon l'API peut appliquer un filtre par défaut.
        filters = {k: v for k, v in filters.items() if v not in (None, "", False)}

        def _fetch_all_pages(base_filters):
            responses = []
            all_content = []

            response = self.api_list_paniers(**base_filters)
            content, meta = self._normalize_list_panier_response(response)
            responses.append(response)
            all_content.extend(content)

            total_pages = meta.get("total_pages")
            page_number = meta.get("page_number")
            page_size = meta.get("page_size")

            if total_pages is not None and page_number is not None:
                try:
                    total_pages = int(total_pages)
                except Exception:
                    total_pages = 0
                try:
                    page_number = int(page_number)
                except Exception:
                    page_number = 0

                while page_number + 1 < total_pages:
                    page_number += 1
                    page_filters = dict(base_filters)
                    if page_size and "size" not in page_filters:
                        page_filters["size"] = page_size
                    # Pagination standard (Spring): page=0..N-1
                    page_filters["page"] = page_number

                    response = self.api_list_paniers(**page_filters)
                    page_content, _page_meta = self._normalize_list_panier_response(response)
                    responses.append(response)
                    all_content.extend(page_content)

            return all_content, meta, responses

        content, meta, responses = _fetch_all_pages(filters)

        # Filtrage côté Odoo si l'API renvoie des lignes incohérentes
        # par rapport au filtre `payer`.
        if "payer" in filters:
            payer_filter = filters.get("payer")
            if isinstance(payer_filter, str):
                payer_filter = payer_filter.strip().lower() in ("true", "1", "yes", "y", "oui")
            payer_filter = bool(payer_filter)
            content = [p for p in content if bool(p.get("payer")) == payer_filter]

        # (Fallback conservé) Si vide et présence d'un appel avec filtres, retenter sans filtre.
        if not content and filters:
            content, meta, responses = _fetch_all_pages({})
            filters = {}

        batch = self._create_batch_from_list_panier_content(
            content=content,
            meta=meta,
            raw_responses=responses,
            params=filters,
            origin_label="list-panier",
            origin_url=f"{self.gateway_url}/list-panier",
        )

        return batch

    def _create_batch_from_list_panier_content(
        self,
        content,
        meta=None,
        raw_responses=None,
        params=None,
        origin_label=None,
        origin_url=None,
    ):
        """Crée un batch + ses lignes à partir d'un contenu list-panier déjà récupéré.

        Utilisé par:
        - fetch_paniers_batch (API)
        - action_import_batch_from_local_json (fichier JSON local)
        """
        self.ensure_one()

        import json as _json

        content = content or []
        meta = meta or {}
        params = params or {}

        now = fields.Datetime.now()
        code = now.strftime("%Y%m%d%H%M%S")

        label = origin_label or "list-panier"
        batch_vals = {
            "name": _("Batch paniers Orbus Infinity %s") % code,
            "code": code,
            "params_json": _json.dumps(params, ensure_ascii=False),
            "raw_response": _json.dumps(raw_responses if raw_responses is not None else content, ensure_ascii=False),
            "status_code": meta.get("status_code"),
            "status": meta.get("status"),
            "message": meta.get("message"),
            "total_elements": meta.get("total_elements"),
            "total_pages": meta.get("total_pages"),
            "page_size": meta.get("page_size"),
            "page_number": meta.get("page_number"),
            "company_id": self.company_id.id,
        }

        batch = self.env["orbus.infinity.panier.batch"].create(batch_vals)

        self._create_api_attachment(
            batch,
            label,
            "GET" if label == "list-panier" else "FILE",
            origin_url or "",
            params,
            raw_responses if raw_responses is not None else content,
        )

        def _to_float(value):
            if value is None:
                return 0.0
            if isinstance(value, str):
                value = value.replace(" ", "").replace(",", ".")
            try:
                return float(value)
            except Exception:
                return 0.0

        def _normalize_dt(value):
            if not value:
                return False
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                val = value.strip()
                # Cas fréquent: "YYYY-MM-DD HH:MM" -> ajouter secondes.
                if len(val) == 16 and re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$", val):
                    val = val + ":00"
                return val
            return value

        line_vals_list = []
        for panier in content:
            if not isinstance(panier, dict):
                continue
            factures = panier.get("factures") or []
            montant_facture = panier.get("montantFacture")
            if montant_facture is None and factures:
                montant_facture = sum(_to_float(f.get("montant")) for f in factures)

            montant_ttc = _to_float(montant_facture)
            destination = panier.get("destination")
            if destination and str(destination).strip().upper() in ("N/A", "NA", "NONE", "NULL"):
                destination = False

            def _destination_to_text(value):
                if not value:
                    return False
                if isinstance(value, dict):
                    return (
                        value.get("name")
                        or value.get("country")
                        or value.get("country_name")
                        or value.get("libelle")
                        or value.get("label")
                        or value.get("value")
                        or value.get("code")
                        or False
                    )
                return str(value)

            destination_text = _destination_to_text(destination) or False

            montant_ht, montant_tva, _apply_vat_18 = self._compute_amounts_for_destination(
                montant_ttc, destination_text
            )

            source = (
                panier.get("source")
                or panier.get("paiementMoyen")
                or panier.get("originePaiement")
                or panier.get("paiementMode")
                or False
            )

            line_vals_list.append(
                {
                    "batch_id": batch.id,
                    "reference_panier": panier.get("referencePanier"),
                    "numero_dossier": panier.get("numeroDossier"),
                    "numero_paiement": panier.get("numeroPaiement"),
                    "source": source,
                    "date_paiement": _normalize_dt(panier.get("datePaiement")),
                    "date_generate_reference": _normalize_dt(panier.get("dateGenerateReference")),
                    "payer": bool(panier.get("payer")),
                    "collectionneur": bool(panier.get("collectionneur")),
                    "transitaire": panier.get("transitaire"),
                    "connaissement": panier.get("connaissement"),
                    "destination": False,
                    "destination_pays": destination_text,
                    "montant_ttc": montant_ttc,
                    "montant_ht": montant_ht,
                    "montant_tva": montant_tva,
                    "factures_json": _json.dumps(factures, ensure_ascii=False),
                    "factures_count": len(factures),
                }
            )

        if line_vals_list:
            self.env["orbus.infinity.panier.batch.line"].create(line_vals_list)

        return batch

    def action_import_batch_from_local_json(self):
        """Bouton: charge un fichier JSON du dossier data/ et crée un batch.

        Le fichier doit être au format list-panier (content + meta).
        """
        self.ensure_one()

        module = "api_orbus_infinity_gainde"
        data_dir = get_module_resource(module, "data")
        if not data_dir or not os.path.isdir(data_dir):
            raise UserError(_("Dossier data introuvable pour le module %s.") % module)

        json_files = [
            name
            for name in os.listdir(data_dir)
            if name.lower().endswith(".json")
        ]
        if not json_files:
            raise UserError(_("Aucun fichier .json trouvé dans %s/data.") % module)

        preferred = [n for n in json_files if n.lower().startswith("json_odoo_exemple")]
        if len(preferred) == 1:
            filename = preferred[0]
        elif len(json_files) == 1:
            filename = json_files[0]
        else:
            raise UserError(
                _(
                    "Plusieurs fichiers JSON sont présents dans data/: %s. "
                    "Merci de n'en garder qu'un seul (ou renommer en json_odoo_exemple*.json)."
                )
                % ", ".join(sorted(json_files))
            )

        file_path = os.path.join(data_dir, filename)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            raise UserError(_("Impossible de lire le fichier JSON %s : %s") % (filename, e)) from e

        content, meta = self._normalize_list_panier_response(payload)
        if not content:
            raise UserError(_("Le fichier %s ne contient aucun panier (content vide).") % filename)

        params = {
            "source": "local_json",
            "file": filename,
        }

        batch = self._create_batch_from_list_panier_content(
            content=content,
            meta=meta,
            raw_responses=payload,
            params=params,
            origin_label=f"local-json:{filename}",
            origin_url=file_path,
        )

        # Assurer l'affichage immédiat des champs calculés stockés.
        batch._compute_totals()
        batch._compute_api_summary_html()

        action = self.env.ref(
            "api_orbus_infinity_gainde.action_orbus_infinity_panier_batch"
        ).read()[0]
        action.update(
            {
                "view_mode": "form",
                "res_id": batch.id,
                "views": [(False, "form")],
            }
        )
        return action

    # ------------------------------------------------------------------
    # Cron
    # ------------------------------------------------------------------
    @api.model
    def cron_fetch_collectionneur_batches(self):
        """Cron: crée un batch list-panier pour `collectionneur=true`.

        Exécution prévue toutes les 2 semaines. On applique une fenêtre de 15 jours
        via `lastFetchedDate` pour limiter le volume.
        """
        configs = self.sudo().search([])
        if not configs:
            return True

        last_fetched = fields.Date.to_string(fields.Date.today() - timedelta(days=15))
        for config in configs:
            try:
                config.fetch_paniers_batch(
                    {
                        "collectionneur": True,
                        "lastFetchedDate": last_fetched,
                    }
                )
            except Exception as e:  # pragma: no cover
                _logger.exception(
                    "[OrbusInfinity][Cron] Erreur batch collectionneur (company=%s): %s",
                    config.company_id.display_name,
                    e,
                )
                continue

        return True

    def create_odoo_invoice_from_panier_line(self, line):
        """Crée une facture Odoo à partir d'une ligne de panier Infinity."""
        self.ensure_one()

        if not line:
            raise UserError(_("Ligne de panier manquante."))

        def _find_account_by_code(code):
            account_model = self.env["account.account"]
            domain = [
                ("code", "=", code),
                ("deprecated", "=", False),
            ]
            if "company_id" in account_model._fields:
                domain.insert(0, ("company_id", "=", self.company_id.id))
            return account_model.search(domain, limit=1)

        taxable_account = _find_account_by_code("706104") or _find_account_by_code("706004")
        exempt_account = _find_account_by_code("706103") or _find_account_by_code("706003")
        vat_account = _find_account_by_code("443200")
        receivable_account = _find_account_by_code("411100")

        if not taxable_account:
            raise UserError(_("Compte de vente taxable (706104/706004) introuvable."))
        if not exempt_account:
            raise UserError(_("Compte de vente non taxable (706103/706003) introuvable."))
        if not vat_account:
            raise UserError(_("Compte TVA (443200) introuvable."))
        if not receivable_account:
            raise UserError(_("Compte client (411100) introuvable."))

        destination = (line.destination_pays or "")
        montant_ht, montant_tva, apply_vat_18 = self._compute_amounts_for_destination(
            line.montant_ttc, destination
        )

        tax_18 = False
        if apply_vat_18:
            tax_18 = self.env["account.tax"].search(
                [
                    ("type_tax_use", "=", "sale"),
                    ("amount_type", "=", "percent"),
                    ("amount", "=", 18),
                    ("company_id", "=", self.company_id.id),
                    ("active", "=", True),
                ],
                limit=1,
            )
            if not tax_18:
                tax_18 = self.env["account.tax"].create(
                    {
                        "name": "TVA 18% Orbus Infinity",
                        "amount": 18.0,
                        "amount_type": "percent",
                        "type_tax_use": "sale",
                        "company_id": self.company_id.id,
                        "invoice_repartition_line_ids": [
                            (0, 0, {"repartition_type": "base", "factor_percent": 100.0}),
                            (0, 0, {"repartition_type": "tax", "factor_percent": 100.0, "account_id": vat_account.id}),
                        ],
                        "refund_repartition_line_ids": [
                            (0, 0, {"repartition_type": "base", "factor_percent": 100.0}),
                            (0, 0, {"repartition_type": "tax", "factor_percent": 100.0, "account_id": vat_account.id}),
                        ],
                    }
                )

        product = self.env["product.product"].search(
            [("name", "=", "Prestation de service Orbus Infinity")],
            limit=1,
        )
        if not product:
            product_vals = {
                "name": "Prestation de service Orbus Infinity",
                "type": "service",
            }
            if tax_18:
                product_vals["taxes_id"] = [(6, 0, [tax_18.id])]
            product = self.env["product.product"].create(product_vals)

        # Partenaire
        partner_name = False
        if line.transitaire:
            partner_name = _("Transitaire %s") % line.transitaire
        else:
            partner_name = _("Client Orbus Infinity")

        partner = self.env["res.partner"].search(
            [("name", "=", partner_name)],
            limit=1,
        )
        if not partner:
            partner = self.env["res.partner"].create(
                {
                    "name": partner_name,
                    "orbus_customer": True,
                }
            )

        partner_receivable_account = receivable_account
        if "tier_partner_account" in partner._fields:
            partner_account_code = partner.tier_partner_account
            if partner_account_code:
                partner_receivable_account = (
                    _find_account_by_code(partner_account_code) or receivable_account
                )

        invoice_date = False
        if line.date_generate_reference:
            try:
                invoice_date = fields.Datetime.to_datetime(line.date_generate_reference).date()
            except Exception:  # pragma: no cover
                invoice_date = False

        label_date = invoice_date or fields.Date.context_today(self)
        label_month_year = format_date(self.env, label_date, date_format="MMMM yyyy")
        line_label = _("Facturation %s") % label_month_year

        factures = line.get_factures()
        line_vals_list = []

        def _add_line(label, amount):
            if amount is None:
                amount = 0.0
            if apply_vat_18:
                # Montant HT taxable (pas de division)
                price_unit = amount
                line_vals = {
                    "name": label,
                    "quantity": 1.0,
                    "price_unit": price_unit,
                    "account_id": taxable_account.id,
                    "tax_ids": [(6, 0, [tax_18.id])] if tax_18 else [(6, 0, [])],
                    "product_id": product.id,
                }
            else:
                line_vals = {
                    "name": label,
                    "quantity": 1.0,
                    "price_unit": amount,
                    "account_id": exempt_account.id,
                    "tax_ids": [(6, 0, [])],
                    "product_id": product.id,
                }
            line_vals_list.append(line_vals)

        if factures:
            for f in factures:
                _add_line(line_label, f.get("montant"))
        else:
            if not line.montant_ttc:
                raise UserError(_("Montant du panier introuvable."))
            _add_line(line_label, line.montant_ttc)

        move_model = self.env["account.move"].with_context(
            default_move_type="out_invoice",
            company_id=self.company_id.id,
        )

        move_vals = {
            "move_type": "out_invoice",
            "partner_id": partner.id,
            "invoice_origin": line.reference_panier,
            "ref": _("Facturation %s") % label_month_year,
            "invoice_line_ids": [(0, 0, vals) for vals in line_vals_list],
            "company_id": self.company_id.id,
            # Références Infinity (suivi)
            "orbus_infinity_reference_panier": line.reference_panier,
            "orbus_infinity_numero_dossier": line.numero_dossier,
            "orbus_infinity_numero_paiement": line.numero_paiement,
            "orbus_infinity_source": line.source,
            "orbus_infinity_date_paiement": line.date_paiement,
            "orbus_infinity_date_generate_reference": line.date_generate_reference,
            "orbus_infinity_payer": line.payer,
            "orbus_infinity_transitaire": line.transitaire,
            "orbus_infinity_connaissement": line.connaissement,
            "orbus_infinity_destination": False,
            "orbus_infinity_destination_pays": line.destination_pays,
            "orbus_infinity_montant_facture": line.montant_ttc,
            "orbus_infinity_factures_json": line.factures_json,
            "orbus_infinity_batch_line_id": line.id,
        }
        if invoice_date:
            move_vals["invoice_date"] = invoice_date

        invoice = move_model.create(move_vals)

        receivable_line = invoice.line_ids.filtered(
            lambda move_line: move_line.account_id.account_type == "asset_receivable"
        )[:1]
        if receivable_line and partner_receivable_account and receivable_line.account_id != partner_receivable_account:
            receivable_line.write({"account_id": partner_receivable_account.id})

        if line.payer:
            self._register_payment_for_invoice(
                invoice,
                source=line.source,
                payment_date=line.date_paiement,
                payment_reference=line.numero_paiement or line.reference_panier,
            )

        return invoice

    def _register_payment_for_invoice(
        self,
        invoice,
        source=None,
        payment_date=None,
        payment_reference=None,
    ):
        """Crée un paiement client pour une facture donnée (montant total).

        Le journal est choisi selon la `source` (moyen de paiement).
        Si `source` est vide/non fournie, on route vers ORBUS INFINITY.
        """
        self.ensure_one()

        if not invoice:
            return False

        if invoice.state == "draft":
            invoice.action_post()

        amount = invoice.amount_residual
        if not amount or amount <= 0:
            return False

        def _norm(val):
            val = (val or "").strip()
            val = unicodedata.normalize("NFKD", val)
            val = "".join(ch for ch in val if not unicodedata.combining(ch))
            val = val.lower()
            return " ".join(val.split())

        source_norm = _norm(source)
        journal_code = False
        if "icrs" in source_norm or "espece" in source_norm or "espèce" in source_norm or "cash" in source_norm:
            journal_code = "ICRS"
        elif "virement" in source_norm or "transfer" in source_norm or "bank" in source_norm:
            journal_code = "ICRS"
        elif "cheque" in source_norm or "chèque" in source_norm or "check" in source_norm:
            journal_code = "ICRS"
        elif "deposit" in source_norm or "depot" in source_norm or "wallet" in source_norm or "on deposit" in source_norm:
            journal_code = "DEP"
        elif "orange" in source_norm or "mobile" in source_norm or "wave" in source_norm or "carte" in source_norm or "card" in source_norm:
            journal_code = "ORBP"
        elif "orbus" in source_norm and ("pai" in source_norm or "payment" in source_norm):
            journal_code = "ORBP"

        if not journal_code:
            raise UserError(_("Moyen de paiement non identifié: %s") % (source or ""))

        journal = self.env["account.journal"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("type", "in", ("bank", "cash")),
                ("code", "=", journal_code),
                ("active", "=", True),
            ],
            limit=1,
        )

        if not journal:
            raise UserError(_("Journal de paiement introuvable pour le code %s.") % journal_code)

        register_model = self.env["account.payment.register"].with_context(
            active_model="account.move",
            active_ids=invoice.ids,
        )

        # Date de paiement issue de l'API (si fournie)
        payment_date_value = fields.Date.context_today(self)
        if payment_date:
            try:
                dt_value = payment_date
                if isinstance(dt_value, str):
                    dt_value = fields.Datetime.to_datetime(dt_value)
                if dt_value:
                    payment_date_value = dt_value.date()
            except Exception:  # pragma: no cover
                payment_date_value = fields.Date.context_today(self)

        vals = {
            "amount": amount,
            "payment_date": payment_date_value,
            "journal_id": journal.id,
        }

        if payment_reference:
            if "payment_reference" in register_model._fields:
                vals["payment_reference"] = payment_reference
            elif "communication" in register_model._fields:
                vals["communication"] = payment_reference

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
