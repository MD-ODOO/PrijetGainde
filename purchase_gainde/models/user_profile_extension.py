from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PurchaseGaindeUserProfile(models.Model):
    _inherit = "user.profiles"

    profile_type = fields.Selection(
        [
            ("rnd", "RND"),
            ("rcb", "RCB"),
            ("ra", "RA"),
            ("assistante_ra", "Assistante RA"),
            ("rm", "Responsable mission"),
            ("da", "DA"),
            ("daf", "DAF"),
            ("rcg", "RCG"),
            ("n1", "N+1"),
            ("compta", "Compta"),
            ("portal", "Portail"),
            ("other", "Autre"),
        ],
        string="Profile Type",
        required=True,
        default="portal",
    )

    profile_manager_id = fields.Many2one(
        "user.management",
        string="Profile Manager",
        readonly=True,
    )

    # @api.model
    # def _gainde_apply_n1_implied_groups(self, *args, **kwargs):
    #     """Assure que tous les profils N+1 ont le groupe PR User en implicite.

    #     Appelé depuis les données XML du module lors des mises à jour,
    #     pour corriger les bases où des profils existaient déjà.
    #     """
    #     group_user = self.env.ref("base.group_user", raise_if_not_found=False)
    #     group_pr_user = self.env.ref(
    #         "purchase_request.group_purchase_request_user", raise_if_not_found=False
    #     )
    #     group_pr_gainde_n1 = self.env.ref(
    #         "purchase_request_gainde.group_purchase_n1", raise_if_not_found=False
    #     )
    #     if not group_user and not group_pr_user and not group_pr_gainde_n1:
    #         return True

    #     n1_profiles = self.search([("profile_type", "=", "n1")])
    #     for profile in n1_profiles:
    #         existing_implied = profile.group_id.implied_ids
    #         implied_ids = existing_implied
    #         if group_user:
    #             implied_ids |= group_user
    #         if group_pr_user:
    #             implied_ids |= group_pr_user
    #         if group_pr_gainde_n1:
    #             implied_ids |= group_pr_gainde_n1
    #         profile.group_id.write({"implied_ids": [(6, 0, implied_ids.ids)]})

    #     # Important: l'écriture ci-dessus se fait sur res.groups (group_id),
    #     # donc access_users_manager ne recalculera pas automatiquement les groupes
    #     # des utilisateurs. On force la synchronisation ici.
    #     if n1_profiles:
    #         n1_profiles.sudo().access_update_users()

    #     return True

    def _gainde_sync_approval_role(self):
        """Créer/synchroniser un rôle d'approbation basé sur le profil.

        - Crée un ``approval.role`` portant le même nom que le profil
          (si inexistant).
        - Ajoute les utilisateurs du profil (``access_user_ids``) sur ce rôle.
        """
        ApprovalRole = self.env["approval.role"].sudo()

        for profile in self:
            name = profile.name
            if not name:
                continue

            # Toujours essayer d'avoir une société : celle du profil ou, à défaut, la société courante
            company = getattr(profile, "company_id", False) or self.env.company
            domain = [("name", "=", name)]

            if "company_id" in ApprovalRole._fields:
                # Si le champ company_id existe (et souvent requis), on filtre sur la société
                domain.append(("company_id", "=", company.id))

            role = ApprovalRole.search(domain, limit=1)

            if not role:
                vals_role = {"name": name}
                if "company_id" in ApprovalRole._fields:
                    vals_role["company_id"] = company.id
                role = ApprovalRole.create(vals_role)

            user_ids = getattr(profile, "access_user_ids", self.env["res.users"]).ids
            if user_ids:
                # On mappe tous les utilisateurs du profil sur le rôle
                role.user_ids = [(6, 0, user_ids)]

    @api.model_create_multi
    def create(self, vals_list):
        # Création du profil (hérite de res.groups via _inherits)
        profiles = super(PurchaseGaindeUserProfile, self).create(vals_list)

        UserManagement = self.env["user.management"].sudo()
        current_company_ids = self.env.company.ids

        # Groupes managers pour les demandes et leurs lignes
        group_user = self.env.ref("base.group_user", raise_if_not_found=False)
        group_pr_manager = self.env.ref(
            "purchase_request.group_purchase_request_manager", raise_if_not_found=False
        )
        # Groupe utilisateur (lecture/accès de base sur purchase.request)
        group_pr_user = self.env.ref(
            "purchase_request.group_purchase_request_user", raise_if_not_found=False
        )
        # Groupe N+1 du module purchase_request_gainde (porte des ACL directes sur purchase.request)
        group_pr_gainde_n1 = self.env.ref(
            "purchase_request_gainde.group_purchase_n1", raise_if_not_found=False
        )
        # Groupe lecture seule comptabilité pour les profils N+1
        group_account_readonly = self.env.ref(
            "account.group_account_readonly", raise_if_not_found=False
        )
        # Groupe manager comptabilité
        group_account_manager = self.env.ref(
            "account.group_account_manager", raise_if_not_found=False
        )
        # Groupes budgétaires Gainde
        group_budget_user = self.env.ref(
            "purchase_gainde.group_budget_user_gainde", raise_if_not_found=False
        )
        group_budget_admin = self.env.ref(
            "purchase_gainde.group_budget_admin_gainde", raise_if_not_found=False
        )
        # Groupes achats
        group_purchase_user = self.env.ref(
            "purchase.group_purchase_user", raise_if_not_found=False
        )
        group_purchase_manager = self.env.ref(
            "purchase.group_purchase_manager", raise_if_not_found=False
        )
        # Groupe portail standard Odoo
        group_portal = self.env.ref("base.group_portal", raise_if_not_found=False)
        # Groupe manager des notes de frais (hr_expense)
        group_expense_manager = self.env.ref(
            "hr_expense.group_hr_expense_manager", raise_if_not_found=False
        )

        for profile, vals in zip(profiles, vals_list):
            # 1) Mapper le(s) groupe(s) manager par défaut sur le groupe associé
            #    pour les profils de type RND/RA/RCG/RCB
            ptype = vals.get("profile_type") or profile.profile_type
            if ptype in {"rnd", "ra", "rcg", "rcb"}:
                # Profils métiers internes : on ajoute les groupes de base + manager PR
                existing_implied = profile.group_id.implied_ids
                implied_ids = existing_implied
                if group_user:
                    implied_ids |= group_user
                if group_pr_manager:
                    implied_ids |= group_pr_manager
                if group_pr_user:
                    implied_ids |= group_pr_user
                # RA : achat utilisateur
                if ptype == "ra" and group_purchase_user:
                    implied_ids |= group_purchase_user
                # RCB : achats manager
                if ptype == "rcb" and group_purchase_manager:
                    implied_ids |= group_purchase_manager
                # RCG : achats manager (accès module Achats / bons de commande)
                if ptype == "rcg" and group_purchase_manager:
                    implied_ids |= group_purchase_manager
                # RCB et RCG portent aussi les droits budgétaires
                if ptype == "rcb" and group_budget_user:
                    implied_ids |= group_budget_user
                if ptype == "rcg" and group_budget_admin:
                    implied_ids |= group_budget_admin
                profile.group_id.write({"implied_ids": [(6, 0, implied_ids.ids)]})
            elif ptype == "n1" and (group_user or group_pr_user or group_pr_gainde_n1 or group_account_readonly or group_pr_manager):
                # Profil N+1 : garantir les groupes nécessaires aux ACL PR dans la stack
                existing_implied = profile.group_id.implied_ids
                implied_ids = existing_implied
                if group_user:
                    implied_ids |= group_user
                if group_pr_user:
                    implied_ids |= group_pr_user
                if group_pr_gainde_n1:
                    implied_ids |= group_pr_gainde_n1
                if group_pr_manager:
                    implied_ids |= group_pr_manager
                if group_account_readonly:
                    implied_ids |= group_account_readonly
                profile.group_id.write({"implied_ids": [(6, 0, implied_ids.ids)]})
            elif ptype == "da" and (group_user or group_purchase_manager or group_budget_admin or group_account_readonly or group_pr_manager):
                # Profil DA : utilisateur interne + purchase manager + gestionnaire budgétaire administrateur + comptabilité lecture seule + purchase request manager
                existing_implied = profile.group_id.implied_ids
                implied_ids = existing_implied
                if group_user:
                    implied_ids |= group_user
                if group_purchase_manager:
                    implied_ids |= group_purchase_manager
                if group_budget_admin:
                    implied_ids |= group_budget_admin
                if group_account_readonly:
                    implied_ids |= group_account_readonly
                if group_pr_manager:
                    implied_ids |= group_pr_manager
                profile.group_id.write({"implied_ids": [(6, 0, implied_ids.ids)]})
            elif ptype == "compta" and group_account_manager:
                # Profil compta : accès manager comptabilité
                existing_implied = profile.group_id.implied_ids
                implied_ids = existing_implied | group_account_manager
                profile.group_id.write({"implied_ids": [(6, 0, implied_ids.ids)]})
            elif ptype == "portal" and group_portal:
                # Profil portail : on force le groupe portail (sans group_user)
                profile.group_id.write({"implied_ids": [(6, 0, [group_portal.id])]})
            elif ptype == "rm" and (group_user or group_expense_manager):
                # Profil RM : groupe interne + manager des notes de frais
                existing_implied = profile.group_id.implied_ids
                implied_ids = existing_implied
                if group_user:
                    implied_ids |= group_user
                if group_expense_manager:
                    implied_ids |= group_expense_manager
                profile.group_id.write({"implied_ids": [(6, 0, implied_ids.ids)]})

            # Les modifications de groupes ci-dessus écrivent sur res.groups (group_id).
            # On synchronise les groupes des utilisateurs du profil.
            profile.sudo().access_update_users()

            # 2) Créer automatiquement le management associé (pack de droits)
            manager_vals = {
                # Nom unique pour éviter le UserError "Name must be unique for managements."
                # On inclut l'ID du profil dans le nom du management.
                "name": f"{profile.name} ({profile.id})",
                "access_profile_ids": [(6, 0, [profile.id])],
                "access_company_ids": [(6, 0, current_company_ids)],
                "is_profile": True,
                # Désactiver systématiquement le mode développeur pour les utilisateurs
                # rattachés à ce profile manager (fonctionnalité access_users_manager).
                "access_disable_debug_mode": True,
            }
            manager = UserManagement.create(manager_vals)
            profile.profile_manager_id = manager.id

            # 3) Créer / synchroniser le rôle d'approbation correspondant
            # "lorsqu'on crée un nouveau user access_manager" : on crée
            # un ``approval.role`` du même nom et on y ajoute les users
            # du profil.
            profile._gainde_sync_approval_role()

        return profiles

    @api.model
    def _gainde_get_assistante_ra_user_ids(self):
        """Retourne les utilisateurs Assistante RA (profile_type = 'assistante_ra')."""
        profiles = self.search([("profile_type", "=", "assistante_ra")])
        user_ids = set()
        for profile in profiles:
            enabled_lines = profile.access_line_ids.filtered(
                lambda line: getattr(line, "access_is_enabled", False)
            )
            user_ids.update(enabled_lines.mapped("access_user_id.id"))
            user_ids.update(profile.access_user_ids.ids)
        return list(user_ids)

    def write(self, vals, remove_disabled_user=False):
        """Extend write to update domain access while keeping base signature.

        The base model `user.profiles` defines `write(self, vals, remove_disabled_user=False)`
        and callers (e.g. access_users_manager) pass this keyword argument. We must
        keep it here and forward it to `super()` to avoid TypeError.
        """
        res = super(PurchaseGaindeUserProfile, self).write(
            vals, remove_disabled_user=remove_disabled_user
        )

        # Si le type passe à N+1, garantir les groupes PR + compta
        if vals.get("profile_type") == "n1":
            group_pr_user = self.env.ref(
                "purchase_request.group_purchase_request_user", raise_if_not_found=False
            )
            group_pr_gainde_n1 = self.env.ref(
                "purchase_request_gainde.group_purchase_n1", raise_if_not_found=False
            )
            group_pr_manager = self.env.ref(
                "purchase_request.group_purchase_request_manager", raise_if_not_found=False
            )
            group_account_readonly = self.env.ref(
                "account.group_account_readonly", raise_if_not_found=False
            )
            if group_pr_user or group_pr_gainde_n1 or group_pr_manager or group_account_readonly:
                for profile in self:
                    existing_implied = profile.group_id.implied_ids
                    implied_ids = existing_implied
                    if group_pr_user:
                        implied_ids |= group_pr_user
                    if group_pr_gainde_n1:
                        implied_ids |= group_pr_gainde_n1
                    if group_pr_manager:
                        implied_ids |= group_pr_manager
                    if group_account_readonly:
                        implied_ids |= group_account_readonly
                    profile.group_id.write({"implied_ids": [(6, 0, implied_ids.ids)]})
                    profile.sudo().access_update_users()

        # Si le type passe à RND, garantir notamment le groupe Purchase Request Manager
        if vals.get("profile_type") == "rnd":
            group_user = self.env.ref("base.group_user", raise_if_not_found=False)
            group_pr_manager = self.env.ref(
                "purchase_request.group_purchase_request_manager", raise_if_not_found=False
            )
            group_pr_user = self.env.ref(
                "purchase_request.group_purchase_request_user", raise_if_not_found=False
            )

            if group_user or group_pr_manager or group_pr_user:
                for profile in self:
                    existing_implied = profile.group_id.implied_ids
                    implied_ids = existing_implied
                    if group_user:
                        implied_ids |= group_user
                    if group_pr_manager:
                        implied_ids |= group_pr_manager
                    if group_pr_user:
                        implied_ids |= group_pr_user
                    profile.group_id.write({"implied_ids": [(6, 0, implied_ids.ids)]})
                    profile.sudo().access_update_users()

        # Si le type passe à RCB ou RCG, garantir les groupes budgétaires associés
        if vals.get("profile_type") in {"rcb", "rcg"}:
            group_budget_user = self.env.ref(
                "purchase_gainde.group_budget_user_gainde", raise_if_not_found=False
            )
            group_budget_admin = self.env.ref(
                "purchase_gainde.group_budget_admin_gainde", raise_if_not_found=False
            )
            group_purchase_manager = self.env.ref(
                "purchase.group_purchase_manager", raise_if_not_found=False
            )
            if group_budget_user or group_budget_admin or group_purchase_manager:
                for profile in self:
                    existing_implied = profile.group_id.implied_ids
                    implied_ids = existing_implied
                    if vals.get("profile_type") == "rcb" and group_budget_user:
                        implied_ids |= group_budget_user
                    if vals.get("profile_type") == "rcg" and group_budget_admin:
                        implied_ids |= group_budget_admin
                    # RCG : accès module Achats / bons de commande
                    if vals.get("profile_type") == "rcg" and group_purchase_manager:
                        implied_ids |= group_purchase_manager
                    profile.group_id.write({"implied_ids": [(6, 0, implied_ids.ids)]})
                    profile.sudo().access_update_users()

        # Si le type passe à Compta, garantir le groupe manager comptabilité
        if vals.get("profile_type") == "compta":
            group_account_manager = self.env.ref(
                "account.group_account_manager", raise_if_not_found=False
            )
            if group_account_manager:
                for profile in self:
                    existing_implied = profile.group_id.implied_ids
                    implied_ids = existing_implied | group_account_manager
                    profile.group_id.write({"implied_ids": [(6, 0, implied_ids.ids)]})
                    profile.sudo().access_update_users()

        # Si le type passe à RM, garantir le groupe manager des notes de frais
        if vals.get("profile_type") == "rm":
            group_user = self.env.ref("base.group_user", raise_if_not_found=False)
            group_expense_manager = self.env.ref(
                "hr_expense.group_hr_expense_manager", raise_if_not_found=False
            )
            if group_user or group_expense_manager:
                for profile in self:
                    existing_implied = profile.group_id.implied_ids
                    implied_ids = existing_implied
                    if group_user:
                        implied_ids |= group_user
                    if group_expense_manager:
                        implied_ids |= group_expense_manager
                    profile.group_id.write({"implied_ids": [(6, 0, implied_ids.ids)]})
                    profile.sudo().access_update_users()

        # Si les utilisateurs du profil changent, on synchronise le rôle
        # d'approbation associé (utilisateurs et éventuellement création).
        if "access_user_ids" in vals or "name" in vals:
            self._gainde_sync_approval_role()

        # Lorsque l'on ajoute/enlève des utilisateurs au profil depuis
        # la fiche profil (access_user_ids), on veut aussi que les packs
        # user.management associés soient recalculés, comme lorsque l'on
        # passe par l'écran d'Access Management.
        # if "access_user_ids" in vals:
        #     managers = self.mapped("profile_manager_id").sudo()
        #     if managers:
        #         managers.access_compute_profile_ids()
        #         managers._gainde_update_domain_access_from_profile_type()

        return res

    # ------------------------------------------------------------
    # DEFAULT PROFILES (INSTALL DATA)
    # ------------------------------------------------------------

    @api.model
    def _gainde_ensure_default_profiles(self):
        """Créer les profils par défaut s'ils n'existent pas déjà.

        Évite les doublons pour les types uniques (RA/DA/RCG) et
        fonctionne même si des profils ont été créés manuellement.
        """
        defaults = [
            ("Profil RND", "rnd"),
            ("Profil RCB", "rcb"),
            ("Profil RA", "ra"),
            ("Profil Assistante RA", "assistante_ra"),
            ("Profil RM", "rm"),
            ("Profil RCG", "rcg"),
            ("Profil N+1", "n1"),
            ("Profil Compta", "compta"),
            ("Profil Portail", "portal"),
            ("Profil Autre", "other"),
        ]
        for name, ptype in defaults:
            exists = self.search([("profile_type", "=", ptype)], limit=1)
            if not exists:
                self.create({"name": name, "profile_type": ptype})

    # ------------------------------------------------------------
    # CONTRAINTE : UN SEUL PROFIL RA / DA / RCG
    # ------------------------------------------------------------

    @api.constrains("profile_type")
    def _check_unique_special_profile_type(self):
        """Garantie l'unicité globale des profils RA, DA, RCG.

        Pour les types de profil "ra", "da" et "rcg", on n'autorise
        qu'un seul enregistrement dans user.profiles.
        """

        special_types = {"ra", "da", "rcg"}
        for profile in self:
            if profile.profile_type not in special_types:
                continue

            domain = [("profile_type", "=", profile.profile_type)]
            if profile.id:
                domain.append(("id", "!=", profile.id))

            other = self.search(domain, limit=1)
            if other:
                raise ValidationError(
                    _(
                        "Only one profile is allowed for type %(ptype)s. "
                        "Please edit the existing profile instead of creating a new one."
                    )
                    % {"ptype": profile.profile_type.upper()}
                )
