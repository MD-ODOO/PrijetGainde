from odoo import api, fields, models


AUDIT_PROFILE_TYPES = {
    "audit_manager": "Audit - Directeur",
    "audit_senior": "Audit - Senior",
    "audit_junior": "Audit - Junior",
}


class GaindeGlobalSyncAuditUserProfiles(models.Model):
    _inherit = "user.profiles"

    profile_type = fields.Selection(
        selection_add=[(key, label) for key, label in AUDIT_PROFILE_TYPES.items()],
        ondelete={key: "set default" for key in AUDIT_PROFILE_TYPES},
    )

    def _gainde_audit_apply_implied_groups(self, profile_type):
        """Ajoute les groupes implicites liés aux profils Audit."""
        self.ensure_one()

        group_user = self.env.ref("base.group_user", raise_if_not_found=False)
        group_map = {
            "audit_manager": self.env.ref(
                "audit_gainde.group_manager", raise_if_not_found=False
            ),
            "audit_senior": self.env.ref(
                "audit_gainde.group_senior", raise_if_not_found=False
            ),
            "audit_junior": self.env.ref(
                "audit_gainde.group_junior", raise_if_not_found=False
            ),
        }

        audit_group = group_map.get(profile_type)
        if not group_user and not audit_group:
            return

        existing_implied = self.group_id.implied_ids
        implied_ids = existing_implied
        if group_user:
            implied_ids |= group_user
        if audit_group:
            implied_ids |= audit_group

        self.group_id.write({"implied_ids": [(6, 0, implied_ids.ids)]})
        self.sudo().access_update_users()

    @api.model_create_multi
    def create(self, vals_list):
        profiles = super().create(vals_list)

        for profile, vals in zip(profiles, vals_list):
            ptype = vals.get("profile_type") or profile.profile_type
            if ptype in AUDIT_PROFILE_TYPES:
                profile._gainde_audit_apply_implied_groups(ptype)

        return profiles

    def write(self, vals, remove_disabled_user=False):
        res = super().write(vals, remove_disabled_user=remove_disabled_user)

        ptype = vals.get("profile_type")
        if ptype in AUDIT_PROFILE_TYPES:
            for profile in self:
                profile._gainde_audit_apply_implied_groups(ptype)

        return res

    @api.model
    def _gainde_ensure_default_profiles(self):
        """Ajoute les profils Audit par défaut en plus des profils Purchase Gainde."""
        res = super()._gainde_ensure_default_profiles()

        profiles_category = self.env.ref(
            "access_users_manager.ir_module_category_profiles", raise_if_not_found=False
        )

        defaults = [
            ("Profil Audit - Directeur", "audit_manager"),
            ("Profil Audit - Senior", "audit_senior"),
            ("Profil Audit - Junior", "audit_junior"),
        ]
        for name, ptype in defaults:
            exists = self.search(
                ["|", ("profile_type", "=", ptype), ("name", "=", name)], limit=1
            )
            if not exists:
                group_domain = [("name", "=", name)]
                if profiles_category:
                    group_domain.append(("category_id", "=", profiles_category.id))
                existing_group = self.env["res.groups"].search(group_domain, limit=1)

                create_vals = {"name": name, "profile_type": ptype}
                if existing_group:
                    create_vals["group_id"] = existing_group.id
                self.create(create_vals)

        return res
