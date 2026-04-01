from odoo import api, fields, models


PROJECT_MGMT_PROFILE_TYPES = {
    "gpm_project_user": "Projets - Collaborateur",
    "gpm_project_manager": "Projets - Chef de Projet",
    "gpm_project_billing": "Projets - Facturation",
    "gpm_project_admin": "Projets - Administrateur",
}


class GaindeGlobalSyncProjectManagementUserProfiles(models.Model):
    _inherit = "user.profiles"

    profile_type = fields.Selection(
        selection_add=[(key, label) for key, label in PROJECT_MGMT_PROFILE_TYPES.items()],
        ondelete={key: "set default" for key in PROJECT_MGMT_PROFILE_TYPES},
    )

    def _gainde_project_management_apply_implied_groups(self, profile_type):
        self.ensure_one()

        group_user = self.env.ref("base.group_user", raise_if_not_found=False)
        group_map = {
            "gpm_project_user": self.env.ref(
                "gainde_project_management.group_project_user", raise_if_not_found=False
            ),
            "gpm_project_manager": self.env.ref(
                "gainde_project_management.group_project_manager", raise_if_not_found=False
            ),
            "gpm_project_billing": self.env.ref(
                "gainde_project_management.group_project_billing", raise_if_not_found=False
            ),
            "gpm_project_admin": self.env.ref(
                "gainde_project_management.group_project_admin", raise_if_not_found=False
            ),
        }

        target_group = group_map.get(profile_type)
        if not group_user and not target_group:
            return

        existing_implied = self.group_id.implied_ids
        implied_ids = existing_implied
        if group_user:
            implied_ids |= group_user
        if target_group:
            implied_ids |= target_group

        self.group_id.write({"implied_ids": [(6, 0, implied_ids.ids)]})
        self.sudo().access_update_users()

    @api.model_create_multi
    def create(self, vals_list):
        profiles = super().create(vals_list)

        for profile, vals in zip(profiles, vals_list):
            ptype = vals.get("profile_type") or profile.profile_type
            if ptype in PROJECT_MGMT_PROFILE_TYPES:
                profile._gainde_project_management_apply_implied_groups(ptype)

        return profiles

    def write(self, vals, remove_disabled_user=False):
        res = super().write(vals, remove_disabled_user=remove_disabled_user)

        ptype = vals.get("profile_type")
        if ptype in PROJECT_MGMT_PROFILE_TYPES:
            for profile in self:
                profile._gainde_project_management_apply_implied_groups(ptype)

        return res

    @api.model
    def _gainde_ensure_default_profiles(self):
        res = super()._gainde_ensure_default_profiles()

        defaults = [
            ("Profil Projets - Collaborateur", "gpm_project_user"),
            ("Profil Projets - Chef de Projet", "gpm_project_manager"),
            ("Profil Projets - Facturation", "gpm_project_billing"),
            ("Profil Projets - Administrateur", "gpm_project_admin"),
        ]

        for name, ptype in defaults:
            exists = self.search([("profile_type", "=", ptype)], limit=1)
            if not exists:
                self.create({"name": name, "profile_type": ptype})

        return res
