from odoo import api, fields, models


class PurchaseGaindeResUsers(models.Model):
    _inherit = "res.users"

    has_profile_rcg = fields.Boolean(
        string="A le profil RCG",
        compute="_compute_gainde_profile_flags",
    )
    has_profile_ra = fields.Boolean(
        string="A le profil RA",
        compute="_compute_gainde_profile_flags",
    )
    has_profile_assistante_ra = fields.Boolean(
        string="A le profil Assistante RA",
        compute="_compute_gainde_profile_flags",
    )
    has_profile_da = fields.Boolean(
        string="A le profil DA",
        compute="_compute_gainde_profile_flags",
    )
    has_profile_daf = fields.Boolean(
        string="A le profil DAF",
        compute="_compute_gainde_profile_flags",
    )

    @api.depends("access_profile_line_ids")
    def _compute_gainde_profile_flags(self):
        ProfileLine = self.env["user.profile.lines"].sudo()
        admin_user = self.env.ref("base.user_admin", raise_if_not_found=False)
        for user in self:
            # Exception admin système : on considère tous les profils actifs
            # pour ne pas bloquer les contrôles fonctionnels côté UI/logique.
            if (admin_user and user.id == admin_user.id) or user.has_group("base.group_system"):
                user.has_profile_rcg = True
                user.has_profile_ra = True
                user.has_profile_assistante_ra = True
                user.has_profile_da = True
                user.has_profile_daf = True
                continue

            lines = ProfileLine.search([
                ("access_user_id", "=", user.id),
                ("active", "=", True),
                ("access_is_enabled", "=", True),
            ])
            profiles = lines.mapped("access_profile_id")
            extra_profiles = getattr(user, "access_profile_ids", self.env["user.profiles"])
            if extra_profiles:
                profiles |= extra_profiles
            types = set(profiles.mapped("profile_type"))
            user.has_profile_rcg = "rcg" in types
            user.has_profile_ra = "ra" in types
            user.has_profile_assistante_ra = "assistante_ra" in types
            user.has_profile_da = "da" in types
            user.has_profile_daf = "daf" in types

    def gainde_get_current_profiles(self):
        """Retourne les profils effectivement actifs pour ces utilisateurs.

        Utilise la logique d'`access_users_manager` basée sur
        ``user.profile.lines.access_is_enabled`` et ``active``.
        """
        self.ensure_one()
        # On ne se base pas sur access_get_enabled_profile (qui mélange
        # lignes et profils) mais directement sur les lignes actives.
        profile_line_model = self.env["user.profile.lines"].sudo()
        lines = profile_line_model.search([
            ("access_user_id", "=", self.id),
            ("active", "=", True),
        ])
        enabled_lines = lines.filtered(lambda l: l.access_is_enabled)
        return enabled_lines.mapped("access_profile_id")

    def _gainde_normalize_login_email(self, login):
        """Normalise le login comme une adresse email en réutilisant
        la logique du module `partner_email_check` si disponible.

        On délègue la normalisation à res.partner._normalize_email qui
        applique les options de la société (syntaxe, délivrabilité...).
        """
        partner_model = self.env["res.partner"]
        normalize_email = getattr(partner_model, "_normalize_email", None)
        if callable(normalize_email) and login:
            return normalize_email(login.strip())
        return login

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            login = vals.get("login")
            if login:
                vals["login"] = self._gainde_normalize_login_email(login)
        return super().create(vals_list)

    def write(self, vals):
        """Étend write pour garantir :

        - la mise à jour des groupes quand les profils changent
          (access_profile_line_ids)
        - et la mise à jour des packs user.management associés, afin
          que les Domain Access soient recalculés, même si l'on travaille
          directement depuis la fiche utilisateur.
        """

        # Profils avant écriture (pour recalculer aussi les anciens packs)
        old_profiles = self.env["user.profiles"]
        if vals.get("access_profile_line_ids"):
            # On mémorise les anciens profils pour recalculer aussi
            # les packs associés à ces profils (et retirer l'utilisateur).
            old_profiles = self.mapped("access_profile_line_ids")
        login = vals.get("login")
        if login:
            vals["login"] = self._gainde_normalize_login_email(login)

        res = super().write(vals)

        if vals.get("access_profile_line_ids"):
            # 1) Recalculer les groupes effectifs à partir des profils
            admin_user = self.env.ref("base.user_admin", raise_if_not_found=False)
            users_to_update = self
            if admin_user:
                users_to_update = users_to_update - admin_user
            if users_to_update:
                users_to_update.sudo().access_update_group_to_user()

            # 2) Mettre à jour les packs user.management associés aux profils
            #    -> anciens + nouveaux profils pour bien retirer l'utilisateur
            #       des anciens packs lorsqu'on remplace/supprime un profil.
            new_profiles = self.mapped("access_profile_line_ids")
            profiles = (old_profiles | new_profiles) if old_profiles else new_profiles
            if profiles:
                managements = (
                    self.env["user.management"]
                    .sudo()
                    .search([("access_profile_ids", "in", profiles.ids)])
                )
                if managements:
                    managements.access_compute_profile_ids()
                    managements._gainde_update_domain_access_from_profile_type()

        return res
