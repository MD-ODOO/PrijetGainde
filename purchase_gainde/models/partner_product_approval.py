from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ResPartnerApproval(models.Model):
    """Ajout de l'engine d'approbation sur les partenaires.

    Deux étapes:
    - Étape 1: RA Achats (utilisateurs profils RA)
    - Étape 2: Responsables comptables (groupe account manager)

    On suit le même pattern que pour purchase.order dans
    xf_approval_route_purchase_back: _name = 'res.partner' et
    _inherit = ['res.partner', 'approval.route.document'] afin
    d'étendre le modèle existant sans créer un nouveau modèle
    technique et sans dupliquer les champs Many2many.
    """

    _name = "res.partner"
    _inherit = ["res.partner", "approval.route.document"]

    approval_state = fields.Selection(
        [
            ("draft", "Brouillon"),
            ("to_approve", "A valider"),
            ("approved", "Approuvé"),
        ],
        string="Etat d'approbation",
        default="draft",
        tracking=True,
    )
    cofi = fields.Char(string="COFI")
    is_supplier_support_vrs = fields.Boolean(string="Support BRS")
    is_cofi_prefix_1 = fields.Boolean(
        string="COFI starts with 1",
        compute="_compute_is_cofi_prefix_1",
    )

    @api.depends("cofi")
    def _compute_is_cofi_prefix_1(self):
        for partner in self:
            cofi = (partner.cofi or "").strip()
            partner.is_cofi_prefix_1 = bool(cofi) and cofi[0] == "1"

    @api.constrains("cofi")
    def _check_cofi_format(self):
        for partner in self:
            if not partner.cofi:
                continue
            cofi = partner.cofi.strip()
            if len(cofi) < 3:
                raise UserError(_("Le champ COFI doit contenir au moins 3 caractères."))
            first, second, third = cofi[0], cofi[1], cofi[2]
            if first not in ("0", "1", "2"):
                raise UserError(_("Le premier caractère de COFI doit être 0, 1 ou 2."))
            if not second.isalpha():
                raise UserError(_("Le deuxième caractère de COFI doit être une lettre."))
            if not third.isdigit():
                raise UserError(_("Le troisième caractère de COFI doit être un chiffre."))




    def _get_default_approval_route_for_company(self, company):
        """Route d'approbation par défaut pour res.partner."""

        route = self.env.ref(
            "purchase_gainde.xf_route_res_partner_default",
            raise_if_not_found=False,
        )
        if route and (not route.company_id or route.company_id.id == company.id):
            return route

        domain = [
            ("model", "=", "res.partner"),
            ("company_id", "in", [company.id, False]),
        ]
        return self.env["approval.route"].search(domain, limit=1)

    def _gainde_is_supplier_candidate(self, vals=None):
        """Détermine si un partner doit entrer dans le circuit fournisseur.

        On se base sur les valeurs à la création/édition quand possible.
        Compatible avec différentes versions/paramétrages (is_supplier, supplier_rank).
        """
        vals = vals or {}
        # Priorité à un flag explicite si présent.
        if "is_supplier" in vals:
            return bool(vals.get("is_supplier"))

        # Standard Odoo: supplier_rank > 0.
        if "supplier_rank" in vals and vals.get("supplier_rank") is not None:
            try:
                return int(vals.get("supplier_rank") or 0) > 0
            except Exception:
                return False

        # Fallback legacy éventuel.
        if "supplier" in vals:
            return bool(vals.get("supplier"))

        return False

    @api.model_create_multi
    def create(self, vals_list):
        """Assigne la route d'approbation par défaut si absente."""

        new_vals_list = []
        for vals in vals_list:
            v = dict(vals)
            # IMPORTANT: la route d'approbation partenaire ne doit s'appliquer
            # qu'aux fournisseurs (pas aux clients).
            if (not v.get("approval_route_id")) and self._gainde_is_supplier_candidate(v):
                company_id = v.get("company_id", self.env.company.id)
                company = self.env["res.company"].browse(company_id)
                route = self._get_default_approval_route_for_company(company)
                if route:
                    v["approval_route_id"] = route.id
            new_vals_list.append(v)

        partners = super(ResPartnerApproval, self).create(new_vals_list)
        return partners

    def write(self, vals):
        """Si un partenaire devient fournisseur, on initialise la route au besoin."""
        res = super(ResPartnerApproval, self).write(vals)

        # Si on change le statut fournisseur et qu'aucune route n'est définie,
        # on assigne la route par défaut.
        if any(k in vals for k in ("is_supplier", "supplier_rank", "supplier")):
            for partner in self:
                is_supplier = bool(getattr(partner, "is_supplier", False))
                if not is_supplier and hasattr(partner, "supplier_rank"):
                    try:
                        is_supplier = int(getattr(partner, "supplier_rank") or 0) > 0
                    except Exception:
                        is_supplier = False
                if is_supplier and not partner.approval_route_id:
                    company = partner.company_id or self.env.company
                    route = partner._get_default_approval_route_for_company(company)
                    if route:
                        partner.approval_route_id = route.id

        return res

    @api.model
    def _gainde_cleanup_partner_approval_for_clients(self):
        """Nettoie les données d'approbation sur les clients (non-fournisseurs).

        Objectif: éviter que des clients aient un workflow/étapes d'approbation
        initialisés alors que le circuit ne s'applique qu'aux fournisseurs.
        """
        Partner = self.env["res.partner"].sudo().with_context(active_test=False)
        domain = [("is_supplier", "=", False)]
        partners = Partner.search(domain)

        if not partners:
            return 0

        # Remettre l'état en brouillon et retirer la route.
        write_vals = {
            "approval_state": "draft",
            "approval_route_id": False,
        }
        partners.write(write_vals)

        # Supprimer les étapes document générées si elles existent.
        if "approval_route_stage_ids" in Partner._fields:
            partners.mapped("approval_route_stage_ids").unlink()

        return len(partners)

    def action_gainde_cleanup_partner_approval_for_clients(self):
        """Action manuelle (UI) : nettoie les clients et notifie."""
        count = self._gainde_cleanup_partner_approval_for_clients()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Nettoyage terminé"),
                "message": _("%s client(s) nettoyé(s) (route/étapes supprimées).") % count,
                "sticky": False,
                "type": "success",
            },
        }

    # -------------------------
    # Helpers approbateurs
    # -------------------------

    def _get_ra_user_ids_from_profiles(self):
        """Retourne les utilisateurs RA Achats (profile_type = 'ra')."""

        Profile = self.env["user.profiles"]
        profiles = Profile.search([("profile_type", "=", "ra")])

        user_ids = set()
        for profile in profiles:
            enabled_lines = profile.access_line_ids.filtered(
                lambda line: getattr(line, "access_is_enabled", False)
            )
            user_ids.update(enabled_lines.mapped("access_user_id.id"))
            user_ids.update(profile.access_user_ids.ids)
        return list(user_ids)

    def _get_account_manager_user_ids(self):
        """Retourne les utilisateurs du profil compta (profile_type = 'compta')."""

        Profile = self.env["user.profiles"]
        profiles = Profile.search([("profile_type", "=", "compta")])

        user_ids = set()
        for profile in profiles:
            enabled_lines = profile.access_line_ids.filtered(
                lambda line: getattr(line, "access_is_enabled", False)
            )
            user_ids.update(enabled_lines.mapped("access_user_id.id"))
            user_ids.update(profile.access_user_ids.ids)
        return list(user_ids)

    def button_approve(self):
        """Lance / fait avancer le circuit d'approbation partenaire."""

        for partner in self:
            # Le circuit d'approbation partenaires est réservé aux fournisseurs.
            if not bool(getattr(partner, "is_supplier", False)):
                raise UserError(_("Le circuit d'approbation ne s'applique qu'aux fournisseurs."))

            # Au moment de l'approbation finale, la TVA doit être renseignée
            if partner.is_supplier:
                if partner.company_type == 'company':
                    if (partner.country_id.code or "").upper() == "SN":
                        if not (partner.vat or "").strip():
                            raise UserError(_("Le champ NINEA est obligatoire pour les partenaires au Sénégal."))
                        if not (partner.cofi or "").strip():
                            raise UserError(_("Le champ COFI est obligatoire pour les partenaires au Sénégal."))
                        if not (partner.rccm or "").strip():
                            raise UserError(_("Le champ RCCM est obligatoire pour les partenaires au Sénégal."))
                else:
                    if not (partner.cin or "").strip():
                        raise UserError(_("Le champ CNI est obligatoire pour approuver ce partenaire."))
              

            # S'assurer qu'une route d'approbation est définie
            if not partner.approval_route_id:
                company = partner.company_id or self.env.company
                route = self._get_default_approval_route_for_company(company)
                if not route:
                    raise UserError(_("Aucune route d'approbation n'est configurée pour les partenaires."))
                partner.approval_route_id = route.id

            # Démarrage du circuit d'approbation si aucune étape encore générée
            if not partner.approval_route_stage_ids and partner.approval_route_id:
                # Générer les étapes de document
                partner.generate_approval_route()

                # Injection des approbateurs RA et comptables sur l'unique étape
                #ra_user_ids = partner._get_ra_user_ids_from_profiles() or []
                am_user_ids = partner._get_account_manager_user_ids() or []

                stages = partner.approval_route_stage_ids.sorted("sequence")
                first_stage = stages[:1]

                if first_stage and (am_user_ids):
                    all_user_ids = list(set(am_user_ids))
                    first_stage.sudo().write({
                        "user_ids": [(6, 0, all_user_ids)],
                    })

                partner.approval_state = "to_approve"
                if partner.next_approval_stage_id:
                    partner._action_send_to_approve()

            # Avancement des approbations
            elif partner.current_approval_stage_id:
                if not partner.tier_account :
                    raise UserError(_("Le champ Compte Tiers est obligatoire pour approuver ce partenaire."))
       
                partner._action_approve()
                if partner._is_fully_approved():
                    partner.approval_state = "approved"

        return True


class ProductTemplateApproval(models.Model):
    """Ajout de l'engine d'approbation sur les articles."""
    _name = "product.template"
    _inherit = ["product.template", "approval.route.document"]

    categ_id = fields.Many2one(
        "product.category",
        string="Catégorie d'article",
        required=False,
    )

    approval_state = fields.Selection(
        [
            ("draft", "Brouillon"),
            ("to_approve", "A valider"),
            ("approved", "Approuvé"),
        ],
        string="Etat d'approbation",
        default="draft",
        tracking=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'categ_id' in res:
            res['categ_id'] = False
        return res

    def _get_default_approval_route_for_company(self, company):
        """Route d'approbation par défaut pour product.template."""

        route = self.env.ref(
            "purchase_gainde.xf_route_product_template_default",
            raise_if_not_found=False,
        )
        if route and (not route.company_id or route.company_id.id == company.id):
            return route

        domain = [
            ("model", "=", "product.template"),
            ("company_id", "in", [company.id, False]),
        ]
        return self.env["approval.route"].search(domain, limit=1)

    @api.model_create_multi
    def create(self, vals_list):
        """Assigne la route d'approbation par défaut si absente."""

        new_vals_list = []
        for vals in vals_list:
            v = dict(vals)
            if not v.get("approval_route_id"):
                company_id = v.get("company_id", self.env.company.id)
                company = self.env["res.company"].browse(company_id)
                route = self._get_default_approval_route_for_company(company)
                if route:
                    v["approval_route_id"] = route.id
            new_vals_list.append(v)

        products = super(ProductTemplateApproval, self).create(new_vals_list)
        return products

    # Reutilise les helpers définis sur res.partner via env

    def _get_ra_user_ids_from_profiles(self):
        """Conserve l'ancien helper pour compatibilité éventuelle."""
        Profile = self.env["user.profiles"]
        profiles = Profile.search([("profile_type", "=", "ra")])

        user_ids = set()
        for profile in profiles:
            enabled_lines = profile.access_line_ids.filtered(
                lambda line: getattr(line, "access_is_enabled", False)
            )
            user_ids.update(enabled_lines.mapped("access_user_id.id"))
            user_ids.update(profile.access_user_ids.ids)
        return list(user_ids)

    def _get_rcg_user_ids_from_profiles(self):
        """Retourne les utilisateurs RCG (profile_type = 'rcg')."""

        Profile = self.env["user.profiles"]
        profiles = Profile.search([("profile_type", "=", "rcg")])

        user_ids = set()
        for profile in profiles:
            enabled_lines = profile.access_line_ids.filtered(
                lambda line: getattr(line, "access_is_enabled", False)
            )
            user_ids.update(enabled_lines.mapped("access_user_id.id"))
            user_ids.update(profile.access_user_ids.ids)
        return list(user_ids)

    def _get_account_manager_user_ids(self):
        """Retourne les utilisateurs du profil compta (profile_type = 'compta')."""
        Profile = self.env["user.profiles"]
        profiles = Profile.search([("profile_type", "=", "compta")])

        user_ids = set()
        for profile in profiles:
            enabled_lines = profile.access_line_ids.filtered(
                lambda line: getattr(line, "access_is_enabled", False)
            )
            user_ids.update(enabled_lines.mapped("access_user_id.id"))
            user_ids.update(profile.access_user_ids.ids)
        return list(user_ids)

    def _get_account_manager_accounting_ids(self):
        """Retourne les utilisateurs du profil compta (profile_type = 'compta')."""
        Profile = self.env["user.profiles"]
        profiles = Profile.search([("profile_type", "=", "compta")])

        user_ids = set()
        for profile in profiles:
            enabled_lines = profile.access_line_ids.filtered(
                lambda line: getattr(line, "access_is_enabled", False)
            )
            user_ids.update(enabled_lines.mapped("access_user_id.id"))
            user_ids.update(profile.access_user_ids.ids)
        return list(user_ids)

    def button_approve(self):
        """Lance / fait avancer le circuit d'approbation article."""

        for product in self:
            # S'assurer qu'une route d'approbation est définie
            if not product.approval_route_id:
                company = product.company_id or self.env.company
                route = self._get_default_approval_route_for_company(company)
                if not route:
                    raise UserError(_("Aucune route d'approbation n'est configurée pour les articles."))
                product.approval_route_id = route.id

            # Démarrage du circuit d'approbation si aucune étape encore générée
            if not product.approval_route_stage_ids and product.approval_route_id:
                product.generate_approval_route()

                # Étape 1 : approbateurs RCG
                rcg_user_ids = product._get_rcg_user_ids_from_profiles() or []
                am_user_ids = product._get_account_manager_accounting_ids() or []

                stages = product.approval_route_stage_ids.sorted("sequence")
                first_stage = stages[:1]    # Étape 1 : Contrôle RCG
                second_stage = stages[1:2]  # Étape 2 : Service comptable

                if first_stage and rcg_user_ids:
                    first_stage.sudo().write({
                        "user_ids": [(6, 0, rcg_user_ids)],
                    })
                if second_stage and am_user_ids:
                    second_stage.sudo().write({
                        "user_ids": [(6, 0, am_user_ids)],
                    })

                product.approval_state = "to_approve"
                if product.next_approval_stage_id:
                    product._action_send_to_approve()

            elif product.current_approval_stage_id:
                # Contraintes par étape :
                # - Étape 1 (Contrôle RCG) : post_id obligatoire
                # - Étape 2 (Service comptable) : catégorie + comptes revenus/dépenses obligatoires
                stage = product.current_approval_stage_id
                if stage.sequence == 1 and not product.post_id:
                    raise UserError(_("Le champ Poste budgétaire est obligatoire pour approuver ce produit à l'étape 1."))
                if stage.sequence == 2:
                    issues = []
                    # Catégorie toujours obligatoire à l'étape 2
                    if not product.categ_id:
                        issues.append(_("Catégorie d'article manquante."))

                    # Cohérence comptes / flags de vente/achat
                    if product.property_account_income_id and not product.sale_ok:
                        issues.append(_("Compte de revenus renseigné alors que l'article n'est pas marqué comme vendable (case 'Est vendu')."))
                    if product.property_account_expense_id and not product.purchase_ok:
                        issues.append(_("Compte de charges renseigné alors que l'article n'est pas marqué comme achetable (case 'Peut être acheté')."))

                    # A minima, au moins un compte doit être renseigné si l'article est vendu ou acheté
                    if (product.sale_ok or product.purchase_ok) and not (
                        product.property_account_income_id or product.property_account_expense_id
                    ):
                        issues.append(_("Au moins un compte (revenus ou charges) doit être renseigné pour cet article."))

                    # Mais un seul compte doit être choisi (revenus OU charges)
                    if product.property_account_income_id and product.property_account_expense_id:
                        issues.append(_("Un seul compte doit être renseigné (revenus OU charges), pas les deux."))

                    if issues:
                        raise UserError(_("Les contrôles suivants bloquent l'approbation de ce produit à l'étape 2 :\n- %s") % "\n- ".join(issues))

                product._action_approve()
                if product._is_fully_approved():
                    product.approval_state = "approved"

        return True
