from odoo import api, fields, models


LEGAL_CONTRACT_PROFILE_TYPES = {
    "legal_assistant": "Assistant Juridique",
    "legal_juriste": "Juriste",
    "legal_resp_juridique": "Responsable Juridique",
    "legal_ag": "AG",
    "legal_ag_interim": "AG Interimaire",
    "legal_audit": "Audit",
}


class GaindeGlobalSyncLegalContractUserProfiles(models.Model):
    _inherit = "user.profiles"

    profile_type = fields.Selection(
        selection_add=[(key, label) for key, label in LEGAL_CONTRACT_PROFILE_TYPES.items()],
        ondelete={key: "set default" for key in LEGAL_CONTRACT_PROFILE_TYPES},
    )

    def _gainde_legal_contract_apply_implied_groups(self, profile_type):
        """Ajoute les groupes implicites liés aux profils Contrats Juridiques."""
        self.ensure_one()

        group_user = self.env.ref("base.group_user", raise_if_not_found=False)
        group_map = {
            "legal_assistant": self.env.ref(
                "gainde_legal_contract.group_ged_ast_juridique", raise_if_not_found=False
            ),
            "legal_juriste": self.env.ref(
                "gainde_legal_contract.group_ged_juridique", raise_if_not_found=False
            ),
            "legal_resp_juridique": self.env.ref(
                "gainde_legal_contract.group_ged_resp_juridique", raise_if_not_found=False
            ),
            "legal_ag": self.env.ref(
                "gainde_legal_contract.group_ged_sign_juridique", raise_if_not_found=False
            ),
            "legal_ag_interim": self.env.ref(
                "gainde_legal_contract.group_ged_sign_juridique", raise_if_not_found=False
            ),
            "legal_audit": self.env.ref(
                "gainde_legal_contract.group_ged_read_juridique", raise_if_not_found=False
            ),
        }

        legal_group = group_map.get(profile_type)
        if not group_user and not legal_group:
            return

        existing_implied = self.group_id.implied_ids
        implied_ids = existing_implied
        if group_user:
            implied_ids |= group_user
        if legal_group:
            implied_ids |= legal_group

        self.group_id.write({"implied_ids": [(6, 0, implied_ids.ids)]})
        self.sudo().access_update_users()

    @api.model_create_multi
    def create(self, vals_list):
        profiles = super().create(vals_list)

        for profile, vals in zip(profiles, vals_list):
            ptype = vals.get("profile_type") or profile.profile_type
            if ptype in LEGAL_CONTRACT_PROFILE_TYPES:
                profile._gainde_legal_contract_apply_implied_groups(ptype)

        return profiles

    def write(self, vals, remove_disabled_user=False):
        res = super().write(vals, remove_disabled_user=remove_disabled_user)

        ptype = vals.get("profile_type")
        if ptype in LEGAL_CONTRACT_PROFILE_TYPES:
            for profile in self:
                profile._gainde_legal_contract_apply_implied_groups(ptype)

        return res

    @api.model
    def _gainde_ensure_default_profiles(self):
        """Ajoute les profils Contrats Juridiques par défaut."""
        res = super()._gainde_ensure_default_profiles()

        profiles_category = self.env.ref(
            "access_users_manager.ir_module_category_profiles", raise_if_not_found=False
        )

        defaults = [
            ("Profil Assistant Juridique", "legal_assistant"),
            ("Profil Juriste", "legal_juriste"),
            ("Profil Responsable Juridique", "legal_resp_juridique"),
            ("Profil AG", "legal_ag"),
            ("Profil AG Interimaire", "legal_ag_interim"),
            ("Profil Audit", "legal_audit"),
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
