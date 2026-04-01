from odoo import models, fields, api


class AccountAnalytic(models.Model):
    _inherit = "account.analytic.account"

    is_budgetary_center = fields.Boolean(
        string="Is Budgetary Center",
        default=False,
        help="Flag to indicate a budget center",
    )
    is_budgetary_poste = fields.Boolean(
        string="Is Budgetary Poste",
        default=False,
        help="Flag to indicate a budget poste",
    )
    bp_user_profile = fields.Many2one(
        comodel_name="user.profiles",
        string="BP User Profile",
        ondelete="set null",
        index=True,
        help="Profil utilisateur lié (pour postes budgétaires)",
    )
    bc_user_profile = fields.Many2one(
        comodel_name="user.profiles",
        string="BC User Profile",
        ondelete="set null",
        index=True,
        help="Profil utilisateur lié (pour centres budgétaires)",
    )

    @api.onchange("is_budgetary_poste", "is_budgetary_center")
    def _onchange_budget_flags(self):
        center_plan = self.env.ref(
            "purchase_gainde.analytic_plan_budget_centers", raise_if_not_found=False
        )
        position_plan = self.env.ref(
            "purchase_gainde.analytic_plan_budget_positions", raise_if_not_found=False
        )

        for rec in self:
            # If poste selected, ensure center is unset and center-profile cleared
            if rec.is_budgetary_poste:
                rec.is_budgetary_center = False
                rec.bc_user_profile = False
                if position_plan:
                    rec.plan_id = position_plan
            # If center selected, ensure poste is unset and poste-profile cleared
            if rec.is_budgetary_center:
                rec.is_budgetary_poste = False
                rec.bp_user_profile = False
                if center_plan:
                    rec.plan_id = center_plan

    @api.constrains("is_budgetary_poste", "is_budgetary_center")
    def _check_exclusive_budget_flags(self):
        for rec in self:
            if rec.is_budgetary_poste and rec.is_budgetary_center:
                raise models.ValidationError(
                    "Un enregistrement ne peut pas être à la fois 'poste' et 'centre budgétaire'."
                )

    # --- Gainde: création automatique du profil RCB pour les centres ---

    def _gainde_ensure_rcb_profile_for_center(self):
        """Créer/relier un profil RCB pour chaque centre budgétaire.

        Pour chaque compte analytique avec ``is_budgetary_center = True`` et
        sans ``bc_user_profile`` :
        - on cherche un profil ``user.profiles`` de type ``rcb`` nommé
          ``RCB_<NOM_DU_COMPTE>`` ;
        - s'il n'existe pas, on le crée ;
        - on le mappe dans ``bc_user_profile``.

        La création du profil déclenche ensuite automatiquement la création
        du manager de profil via l'extension de ``user.profiles``.
        """
        UserProfile = self.env["user.profiles"].sudo()
        for rec in self:
            if rec.is_budgetary_center and not rec.bc_user_profile:
                base_name = rec.name or rec.display_name or str(rec.id)
                profile_name = f"RCB_{base_name}"
                profile = UserProfile.search(
                    [
                        ("name", "=", profile_name),
                        ("profile_type", "=", "rcb"),
                    ],
                    limit=1,
                )
                if not profile:
                    # On désactive la génération immédiate des Domain Access
                    # pendant la création automatique liée au centre budgétaire.
                    profile = UserProfile.with_context(gainde_skip_domain_update=True).create(
                        {
                            "name": profile_name,
                            "profile_type": "rcb",
                        }
                    )
                rec.bc_user_profile = profile.id

    @api.model_create_multi
    def create(self, vals_list):
        """Ajuste automatiquement le plan analytique et le profil RCB.

        - Si ``is_budgetary_center`` est vrai et qu'aucun ``plan_id`` n'est
          fourni, on mappe sur le plan "Centres budgétaires".
        - La logique de création/mapping du profil RCB reste inchangée.
        """

        Plan = self.env["account.analytic.plan"]
        center_plan = self.env.ref(
            "purchase_gainde.analytic_plan_budget_centers", raise_if_not_found=False
        )
        position_plan = self.env.ref(
            "purchase_gainde.analytic_plan_budget_positions", raise_if_not_found=False
        )

        for vals in vals_list:
            is_center = vals.get("is_budgetary_center")
            is_poste = vals.get("is_budgetary_poste")
            # Ne pas écraser un plan explicitement fourni
            if not vals.get("plan_id"):
                if is_center and center_plan:
                    vals["plan_id"] = center_plan.id
                elif is_poste and position_plan:
                    vals["plan_id"] = position_plan.id

        records = super(AccountAnalytic, self).create(vals_list)
        records._gainde_ensure_rcb_profile_for_center()
        return records

    def write(self, vals):
        """Maintient le plan analytique cohérent lors des changements de type.

        - Si on coche ``is_budgetary_center`` sans plan, on force le plan
          "Centres budgétaires".
        - Si on coche ``is_budgetary_poste`` sans plan, on force le plan
          "Postes budgétaires".
        - On conserve la logique existante de création/mapping RCB.
        """

        center_plan = self.env.ref(
            "purchase_gainde.analytic_plan_budget_centers", raise_if_not_found=False
        )
        position_plan = self.env.ref(
            "purchase_gainde.analytic_plan_budget_positions", raise_if_not_found=False
        )

        res = super(AccountAnalytic, self).write(vals)

        # Post-traitement sur les enregistrements mis à jour
        for rec in self:
            if vals.get("is_budgetary_center") and not rec.plan_id and center_plan:
                rec.plan_id = center_plan.id
            if vals.get("is_budgetary_poste") and not rec.plan_id and position_plan:
                rec.plan_id = position_plan.id

        # Si on modifie le flag centre ou le mapping, on s'assure que
        # tout centre budgétaire a bien son profil RCB.
        if "is_budgetary_center" in vals or "bc_user_profile" in vals:
            self._gainde_ensure_rcb_profile_for_center()
        return res
