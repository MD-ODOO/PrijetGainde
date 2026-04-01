from odoo import models, api,exceptions, _


class PurchaseGaindeUserManagement(models.Model):
    _inherit = "user.management"

    # def _gainde_get_apps_menu_ids(self):
    #     """Retourne les menus racine (apps) à masquer par défaut."""
    #     return self.env["ir.ui.menu"].sudo().search([("parent_id", "=", False)]).ids

    # @api.model
    # def default_get(self, fields_list):
    #     res = super(PurchaseGaindeUserManagement, self).default_get(fields_list)
    #     if "access_hide_menu_ids" in fields_list and not res.get("access_hide_menu_ids"):
    #         menu_ids = self._gainde_get_apps_menu_ids()
    #         if menu_ids:
    #             res["access_hide_menu_ids"] = [(6, 0, menu_ids)]
    #     return res

    def _gainde_get_profile_for_domain(self):
        """Retourne le profil principal utilisé pour calculer les domaines.

        On prend le premier profil ayant un champ ``profile_type`` défini.
        """
        self.ensure_one()
        profile = self.access_profile_ids.filtered(lambda p: getattr(p, "profile_type", False))[:1]
        return profile or self.env["user.profiles"]

    def _gainde_get_purchase_request_domain(self, profile_type, profile_ids):
        """Domaine dynamique pour le modèle ``purchase.request`` selon le type de profil.

        On retourne une chaîne représentant un domaine Odoo, exploitable par
        ``domain.access`` / ``ir.rule`` (avec ``user.id`` dynamique).
        """
        if profile_type == "rnd":
            # Demandes où l'utilisateur est le demandeur, ou liées au pack via la catégorie
            return "['|', ('requested_by', '=', user.id), ('line_ids.product_id.categ_id.user_profile_id', 'in', %s)]" % profile_ids

        if profile_type == "rcb":
            # Demandes :
            #  - créées par l'utilisateur
            #  - OU ayant au moins une ligne dont la distribution analytique
            #    pointe vers un centre budgétaire rattaché à un profil du pack
            return "['|', ('create_uid', '=', user.id), ('line_ids.distribution_analytic_account_ids.bc_user_profile', 'in', %s)]" % profile_ids

        if profile_type == "n1":
            # Demandes où l'utilisateur est créateur, demandeur ou coach approbateur.
            return "['|', ('create_uid', '=', user.id), '|', ('requested_by', '=', user.id), ('requested_by.employee_id.coach_id.user_id', '=', user.id)]"

        if profile_type in ("rcg", "portal"):
            # Pas de restriction spécifique côté demande pour ces profils.
            return "[]"

        # Par défaut, aucun filtrage supplémentaire au niveau des demandes.
        return "[]"

    def _gainde_get_purchase_request_line_domain(self, profile_type, profile_ids):
        """Domaine dynamique pour ``purchase.request.line`` selon le type de profil."""
        if profile_type == "rnd":
            # Lignes :
            #  - dont la demande associée est créée par l'utilisateur
            #  - OU dont la catégorie produit pointe vers un profil du pack
            return "['|', ('request_id.create_uid', '=', user.id), ('product_id.categ_id.user_profile_id', 'in', %s)]" % profile_ids

        if profile_type == "rcb":
            # Lignes :
            #  - créées par l'utilisateur
            #  - OU dont la demande associée est créée par l'utilisateur
            #  - OU dont le poste budgétaire est rattaché à un profil du pack
            return "['|', '|', ('create_uid', '=', user.id), ('request_id.create_uid', '=', user.id), ('distribution_analytic_account_ids.bc_user_profile', 'in', %s)]" % profile_ids

        if profile_type == "n1":
            # Lignes où l'utilisateur est créateur, demandeur ou coach.
            return "['|', ('create_uid', '=', user.id), '|', ('request_id.requested_by', '=', user.id), ('request_id.requested_by.employee_id.coach_id.user_id', '=', user.id)]"

        # Par défaut, aucun filtrage spécifique sur les lignes.
        return "[]"

    def _gainde_get_domain_definitions(self, profile_type):
        """Définitions des Domain Access par type de profil.

        Chaque entrée doit retourner une liste de dictionnaires compatibles avec
        ``domain.access.create`` (sans ``access_user_management_id`` qui sera ajouté).

        À adapter fonctionnellement selon vos besoins métier.
        """
        self.ensure_one()
        ir_model = self.env["ir.model"]

        # Exemple : restriction sur les demandes d'achat, leurs lignes,
        # et certains objets budgétaires (centres budgétaires notamment).
        pr_model = ir_model.search([("model", "=", "purchase.request")], limit=1)
        pr_line_model = ir_model.search([("model", "=", "purchase.request.line")], limit=1)
        budget_analytic_model = ir_model.search([("model", "=", "budget.analytic")], limit=1)
        budget_line_model = ir_model.search([("model", "=", "budget.line")], limit=1)
        po_model = ir_model.search([("model", "=", "purchase.order")], limit=1)
        po_line_model = ir_model.search([("model", "=", "purchase.order.line")], limit=1)
        approval_stage_model = ir_model.search([("model", "=", "approval.route.document.stage")], limit=1)

        if not pr_model or not pr_line_model:
            return []

        profile_ids = self.access_profile_ids.ids or []
        pr_domain = self._gainde_get_purchase_request_domain(profile_type, profile_ids)
        pr_line_domain = self._gainde_get_purchase_request_line_domain(profile_type, profile_ids)
        # Domain sur les centres budgétaires :
        #  - is_budgetary_center = True
        #  - bc_user_profile dans les profils du pack courant
        #centers_domain = "[('is_budgetary_center', '=', True), ('bc_user_profile', 'in', %s)]" % profile_ids
        mapping = {
            # R&D : demandes en RND + lignes liées aux profils du pack via la catégorie
            "rnd": [
                {
                    # Demandes en état RND liées à au moins une ligne
                    # dont la catégorie produit pointe vers un profil de ce pack,
                    # ou créées par l'utilisateur lui-même
                    "access_model_id": pr_model.id,
                    "access_read_access": True,
                    "access_write_access": True,
                    "access_create_access": True,
                    "access_delete_access": False,
                    "access_apply_domain": True,
                    "access_domain": pr_domain,
                },
                {
                    # Lignes dont la catégorie produit pointe vers un profil de ce pack
                    # ou créées par l'utilisateur lui-même
                    "access_model_id": pr_line_model.id,
                    "access_read_access": True,
                    "access_write_access": True,
                    "access_create_access": True,
                    "access_delete_access": False,
                    "access_apply_domain": True,
                    "access_domain": pr_line_domain,
                },
            ],
            # RCB : demandes RCB + lignes liées aux profils via le poste budgétaire
            "rcb": [
                {
                    # Demandes en état RCB
                    "access_model_id": pr_model.id,
                    "access_read_access": True,
                    "access_write_access": True,
                    "access_create_access": False,
                    "access_delete_access": False,
                    "access_apply_domain": True,
                    "access_domain": pr_domain,
                },
                {
                    # Lignes dont le poste budgétaire est rattaché à un profil de ce pack
                    # ou créées par l'utilisateur lui-même
                    "access_model_id": pr_line_model.id,
                    "access_read_access": True,
                    "access_write_access": True,
                    "access_create_access": False,
                    "access_delete_access": False,
                    "access_apply_domain": True,
                    "access_domain": pr_line_domain,
                },
                # Centres budgétaires rattachés aux profils du pack
                # (si le modèle analytic existe dans la base)
                # (
                #     [
                #         {
                #             "access_model_id": analytic_model.id,
                #             "access_read_access": True,
                #             "access_write_access": False,
                #             "access_create_access": False,
                #             "access_delete_access": False,
                #             "access_apply_domain": True,
                #             "access_domain": centers_domain,
                #         }
                #     ]
                #     if analytic_model
                #     else []
                # ),
            ],
            # RA : exemple, accès aux demandes à traiter par les achats
            "ra": [
                # {
                #     "access_model_id": pr_model.id,
                #     "access_read_access": True,
                #     "access_write_access": True,
                #     "access_create_access": False,
                #     "access_delete_access": False,
                #     "access_apply_domain": True,
                #     "access_domain": "[]",
                # }
            ],
            # RCG : accès demandes + bons de commande + approbations + répartitions analytiques
            "rcg": [
                {
                    "access_model_id": pr_model.id,
                    "access_read_access": True,
                    "access_write_access": True,
                    "access_create_access": False,
                    "access_delete_access": False,
                    "access_apply_domain": True,
                    "access_domain": pr_domain,
                },
            ]
            # Accès à tous les bons de commande (purchase.order)
            + (
                [
                    {
                        "access_model_id": po_model.id,
                        "access_read_access": True,
                        "access_write_access": True,
                        "access_create_access": False,
                        "access_delete_access": False,
                        "access_apply_domain": True,
                        "access_domain": "[]",
                    }
                ]
                if po_model
                else []
            )
            # Accès aux lignes des bons de commande (purchase.order.line)
            + (
                [
                    {
                        "access_model_id": po_line_model.id,
                        "access_read_access": True,
                        "access_write_access": True,
                        "access_create_access": False,
                        "access_delete_access": False,
                        "access_apply_domain": True,
                        "access_domain": "[]",
                    }
                ]
                if po_line_model
                else []
            )
            # Lecture de toutes les approbations (approval.route.document.stage)
            + (
                [
                    {
                        "access_model_id": approval_stage_model.id,
                        "access_read_access": True,
                        "access_write_access": False,
                        "access_create_access": False,
                        "access_delete_access": False,
                        "access_apply_domain": True,
                        "access_domain": "[]",
                    }
                ]
                if approval_stage_model
                else []
            )
            # Modification des répartitions analytiques (budget.analytic)
            + (
                [
                    {
                        "access_model_id": budget_analytic_model.id,
                        "access_read_access": True,
                        "access_write_access": True,
                        "access_create_access": False,
                        "access_delete_access": False,
                        "access_apply_domain": True,
                        "access_domain": "[]",
                    }
                ]
                if budget_analytic_model
                else []
            ),
            # DA : domaines ouverts (pas de restriction) notamment sur le budget
            "da": [
                {
                    "access_model_id": pr_model.id,
                    "access_read_access": True,
                    "access_write_access": True,
                    "access_create_access": True,
                    "access_delete_access": False,
                    "access_apply_domain": True,
                    "access_domain": "[]",
                },
                {
                    "access_model_id": pr_line_model.id,
                    "access_read_access": True,
                    "access_write_access": True,
                    "access_create_access": True,
                    "access_delete_access": False,
                    "access_apply_domain": True,
                    "access_domain": "[]",
                },
            ]
            + (
                [
                    {
                        "access_model_id": budget_analytic_model.id,
                        "access_read_access": True,
                        "access_write_access": True,
                        "access_create_access": True,
                        "access_delete_access": False,
                        "access_apply_domain": True,
                        "access_domain": "[]",
                    }
                ]
                if budget_analytic_model
                else []
            )
            + (
                [
                    {
                        "access_model_id": budget_line_model.id,
                        "access_read_access": True,
                        "access_write_access": True,
                        "access_create_access": True,
                        "access_delete_access": False,
                        "access_apply_domain": True,
                        "access_domain": "[]",
                    }
                ]
                if budget_line_model
                else []
            ),
            # N+1 : accès aux lignes et demandes où l'utilisateur est coach approbateur
            "n1": [
                {
                    # Lignes :
                    #  - soit l'utilisateur est coach approbateur
                    #  - soit il est le demandeur (requested_by)
                    #  - soit il est le créateur de la ligne
                    "access_model_id": pr_line_model.id,
                    "access_read_access": True,
                    "access_write_access": True,
                    "access_create_access": True,
                    "access_delete_access": False,
                    "access_apply_domain": True,
                    # Domain : créateur OU (demandeur OU coach)
                    "access_domain": pr_line_domain,
                },
                {
                    # Demandes :
                    #  - soit l'utilisateur est coach approbateur
                    #  - soit il est le demandeur
                    #  - soit il est le créateur de la demande
                    "access_model_id": pr_model.id,
                    "access_read_access": True,
                    "access_write_access": True,
                    "access_create_access": True,
                    "access_delete_access": False,
                    "access_apply_domain": True,
                    # Domain : créateur OU (demandeur OU coach)
                    "access_domain": pr_domain,
                },
            ],
            # Portal : exemple très ouvert, à adapter (ici aucune restriction spécifique)
            "portal": [
                {
                    "access_model_id": pr_model.id,
                    "access_read_access": True,
                    "access_write_access": False,
                    "access_create_access": False,
                    "access_delete_access": False,
                    "access_apply_domain": True,
                    "access_domain": pr_domain,
                }
            ],
        }

        return mapping.get(profile_type, [])

    # def access_compute_profile_ids(self):
    #     """Compute robuste des utilisateurs liés aux profils."""
    #     for rec in self:
    #         users = rec.access_profile_ids.mapped("access_user_ids").ids
    #         rec.access_user_ids = [(6, 0, users)]
    #         rec.access_user_rel_ids = [(6, 0, users)]

    def _gainde_update_domain_access_from_profile_type(self, reset=False):
        """(Re)génère les lignes Domain Access selon le type de profil lié.

        - Si ``reset`` est False (comportement par défaut), on NE TOUCHE PAS
          aux lignes Domain Access déjà présentes pour ce pack. Cela permet
          de conserver toutes les règles créées/ajustées manuellement depuis
          l'interface, même si le type de profil change ou que des profils
          sont ajoutés.
        - Si ``reset`` est True, on supprime d'abord toutes les lignes
          existantes (`access_domain_access_line.unlink()`), puis on recrée
          les domaines "initiaux" en fonction du ``profile_type``.

        On évite dans tous les cas de générer ces règles pendant
        l'installation/mise à jour des modules (contexte ``install_mode``),
        car le module ``access_users_manager`` crée et ajuste aussi des
        règles et cela peut provoquer des erreurs de cohérence pendant le
        chargement initial des données.
        """
        # Ne rien faire pendant l'installation des modules, les domaines
        # seront régénérés dès que l'on modifiera les profils/pack ensuite.
        # On peut aussi désactiver explicitement via un flag de contexte
        # (utilisé lors de certaines créations automatiques, ex: catégories).
        if self.env.context.get("install_mode") or self.env.context.get("gainde_skip_domain_update"):
            return
        DomainAccess = self.env["domain.access"].sudo()

        for management in self:
            profile = management._gainde_get_profile_for_domain()
            profile_type = getattr(profile, "profile_type", False)

            if not profile_type:
                continue

            # Par défaut (reset=False), on ne modifie pas les lignes déjà
            # existantes afin de ne pas écraser les règles saisies à la main.
            if not reset and management.access_domain_access_line:
                continue

            if reset:
                # Mode "reset" explicite : on repart d'une feuille blanche.
                management.access_domain_access_line.unlink()

            domain_defs = management._gainde_get_domain_definitions(profile_type)
            for vals in domain_defs:
                vals_with_mgmt = dict(vals, access_user_management_id=management.id)
                DomainAccess.create(vals_with_mgmt)

    def action_gainde_reset_domain_access(self):
        """Action bouton: régénère les Domain Access par défaut.

        - Utilisée depuis la vue pour "recharger" les domaines initiaux
          en fonction du type de profil.
        - Laisse ensuite l'utilisateur libre de modifier manuellement
          les lignes générées.

        On appelle ici `_gainde_update_domain_access_from_profile_type` en
        mode ``reset=True`` pour forcer la régénération complète.
        """
        self._gainde_update_domain_access_from_profile_type(reset=True)
        # Pas d'action spécifique à renvoyer; un simple rafraîchissement
        # côté client suffit généralement.
        return True

    @api.model_create_multi
    def create(self, vals_list):
        """Crée les Domain Access une seule fois à la création.

        Ensuite, tout changement de profils devra être pris en compte
        manuellement via le bouton "Recharger les domaines".
        """
        # menu_ids = self._gainde_get_apps_menu_ids()
        # if menu_ids:
        #     for vals in vals_list:
        #         if not vals.get("access_hide_menu_ids"):
        #             vals["access_hide_menu_ids"] = [(6, 0, menu_ids)]
        records = super(PurchaseGaindeUserManagement, self).create(vals_list)
        # À la création du pack, on génère les domaines initiaux une seule
        # fois, en mode "reset" explicite.
        records._gainde_update_domain_access_from_profile_type(reset=True)
        return records

    # @api.depends("access_profile_ids", "access_profile_ids.access_user_ids")
    # def access_compute_profile_ids(self):
    #     """Étend le compute d'origine pour synchroniser les utilisateurs
    #     des règles de domaine quand les profils ou leurs utilisateurs changent.

    #     Cas fonctionnel que tu décris :
    #     - 1er utilisateur dans un profil/pack : le domaine est bon.
    #     - 2e utilisateur ajouté au même profil : le domaine reste
    #       effectif seulement pour le 1er, car les groupes de la règle
    #       ne sont pas mis à jour.

    #     Ici, on appelle le compute d'origine (super) qui remplit
    #     ``access_user_ids`` à partir des profils, puis on recalcule
    #     les utilisateurs sur les ``ir.rule`` liés aux Domain Access.
    #     """
    #     super(PurchaseGaindeUserManagement, self).access_compute_profile_ids()

    #     for management in self:
    #         users = management.access_user_ids
    #         if not users:
    #             continue
    #         for domain in management.access_domain_access_line:
    #             if domain.access_rule_id and domain.access_rule_id.groups:
    #                 domain.access_rule_id.groups.users = [(6, 0, users.ids)]
