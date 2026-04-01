from odoo import api, fields, models


ASSET_PROFILE_TYPES = {
    "asset_user": "Immobilisations - Utilisateur",
    "asset_admin": "Immobilisations - Administrateur",
    "asset_maintenance_user": "Maintenance - Utilisateur",
    "asset_maintenance_admin": "Maintenance - Administrateur",
    "asset_depreciation_user": "Amortissements - Utilisateur",
    "asset_depreciation_admin": "Amortissements - Administrateur",
    "asset_transfer_user": "Transferts - Utilisateur",
    "asset_transfer_admin": "Transferts - Administrateur",
    "asset_reporting_admin": "Reporting - Administrateur",
    "asset_vendor_user": "Fournisseurs Immob. - Utilisateur",
    "asset_vendor_admin": "Fournisseurs Immob. - Administrateur",
}


class GaindeGlobalSyncAssetUserProfiles(models.Model):
    _inherit = "user.profiles"

    profile_type = fields.Selection(
        selection_add=[(key, label) for key, label in ASSET_PROFILE_TYPES.items()],
        ondelete={key: "set default" for key in ASSET_PROFILE_TYPES},
    )

    def _gainde_asset_apply_implied_groups(self, profile_type):
        """Ajoute les groupes implicites liés aux profils Asset Management."""
        self.ensure_one()

        group_user = self.env.ref("base.group_user", raise_if_not_found=False)
        group_map = {
            "asset_user": self.env.ref(
                "asset_management.assets_user_group", raise_if_not_found=False
            ),
            "asset_admin": self.env.ref(
                "asset_management.assets_admin_group", raise_if_not_found=False
            ),
            "asset_maintenance_user": self.env.ref(
                "asset_management.maintenance_user_group", raise_if_not_found=False
            ),
            "asset_maintenance_admin": self.env.ref(
                "asset_management.maintenance_admin_group", raise_if_not_found=False
            ),
            "asset_depreciation_user": self.env.ref(
                "asset_management.depreciation_user_group", raise_if_not_found=False
            ),
            "asset_depreciation_admin": self.env.ref(
                "asset_management.depreciation_admin_group", raise_if_not_found=False
            ),
            "asset_transfer_user": self.env.ref(
                "asset_management.transfer_user_group", raise_if_not_found=False
            ),
            "asset_transfer_admin": self.env.ref(
                "asset_management.transfer_admin_group", raise_if_not_found=False
            ),
            "asset_reporting_admin": self.env.ref(
                "asset_management.reporting_admin_group", raise_if_not_found=False
            ),
            "asset_vendor_user": self.env.ref(
                "asset_management.vendor_user_group", raise_if_not_found=False
            ),
            "asset_vendor_admin": self.env.ref(
                "asset_management.vendor_admin_group", raise_if_not_found=False
            ),
        }

        asset_group = group_map.get(profile_type)
        if not group_user and not asset_group:
            return

        existing_implied = self.group_id.implied_ids
        implied_ids = existing_implied
        if group_user:
            implied_ids |= group_user
        if asset_group:
            implied_ids |= asset_group

        self.group_id.write({"implied_ids": [(6, 0, implied_ids.ids)]})
        self.sudo().access_update_users()

    @api.model_create_multi
    def create(self, vals_list):
        profiles = super().create(vals_list)

        for profile, vals in zip(profiles, vals_list):
            ptype = vals.get("profile_type") or profile.profile_type
            if ptype in ASSET_PROFILE_TYPES:
                profile._gainde_asset_apply_implied_groups(ptype)

        return profiles

    def write(self, vals, remove_disabled_user=False):
        res = super().write(vals, remove_disabled_user=remove_disabled_user)

        ptype = vals.get("profile_type")
        if ptype in ASSET_PROFILE_TYPES:
            for profile in self:
                profile._gainde_asset_apply_implied_groups(ptype)

        return res

    @api.model
    def _gainde_ensure_default_profiles(self):
        """Ajoute les profils Asset Management par défaut."""
        res = super()._gainde_ensure_default_profiles()

        profiles_category = self.env.ref(
            "access_users_manager.ir_module_category_profiles", raise_if_not_found=False
        )

        defaults = [
            ("Profil Immobilisations - Utilisateur", "asset_user"),
            ("Profil Immobilisations - Administrateur", "asset_admin"),
            ("Profil Maintenance - Utilisateur", "asset_maintenance_user"),
            ("Profil Maintenance - Administrateur", "asset_maintenance_admin"),
            ("Profil Amortissements - Utilisateur", "asset_depreciation_user"),
            ("Profil Amortissements - Administrateur", "asset_depreciation_admin"),
            ("Profil Transferts - Utilisateur", "asset_transfer_user"),
            ("Profil Transferts - Administrateur", "asset_transfer_admin"),
            ("Profil Reporting - Administrateur", "asset_reporting_admin"),
            ("Profil Fournisseurs Immob. - Utilisateur", "asset_vendor_user"),
            ("Profil Fournisseurs Immob. - Administrateur", "asset_vendor_admin"),
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
