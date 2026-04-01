from odoo import api, models, _
from odoo.exceptions import UserError


class GaindeAnalyticDistributionMixin(models.AbstractModel):
    _name = "gainde.analytic.distribution.mixin"
    _description = "Gainde Analytic Distribution Helper"

    @api.model
    def _gainde_compute_analytic_distribution_map(self, product, department=None):
        if not product:
            return {}

        poste = None
        tmpl = product.product_tmpl_id
        if "post_id" in tmpl._fields:
            poste = tmpl.post_id
        if not poste and "post_id" in product._fields:
            poste = product.post_id

        if not poste:
            raise UserError(
                _("Poste budgétaire introuvable pour le produit %s")
                % (product.display_name,)
            )

        Budget = self.env["budget.analytic"].sudo()
        AnalyticAccount = self.env["account.analytic.account"]

        poste_id = poste.id
        bl_center_map = {}
        all_centers = AnalyticAccount

        for budget in Budget.search([]):
            for bl in budget.budget_line_ids:
                poste_matched = False
                centers_for_bl = AnalyticAccount

                for fname, fdef in bl._fields.items():
                    if getattr(fdef, "comodel_name", None) != "account.analytic.account":
                        continue
                    if fdef.type not in ("many2one", "many2many"):
                        continue

                    recs = getattr(bl, fname) or AnalyticAccount

                    if poste_id in recs.ids and any(a.is_budgetary_poste for a in recs):
                        poste_matched = True

                    centers_for_bl |= recs.filtered(lambda a: a.is_budgetary_center)

                if poste_matched and centers_for_bl:
                    bl_center_map[bl.id] = centers_for_bl
                    all_centers |= centers_for_bl

        if not all_centers:
            raise UserError(
                _("Aucun centre trouvé pour le poste %s") % (poste.display_name,)
            )

        center = None
        if len(all_centers) == 1:
            center = all_centers[0]
        else:
            dept_centers = AnalyticAccount
            if department:
                current_dept = department
                while current_dept and not dept_centers:
                    dept_budget = Budget.search([("department_id", "=", current_dept.id)], limit=1)
                    if dept_budget:
                        for bl in dept_budget.budget_line_ids:
                            dept_centers |= bl_center_map.get(bl.id, AnalyticAccount)
                    current_dept = current_dept.parent_id

            scope = dept_centers or all_centers
            if len(scope) == 1:
                center = scope[0]
            else:
                profile = getattr(poste, "bp_user_profile", False)
                profile_centers = (
                    scope.filtered(lambda c: c.bc_user_profile == profile)
                    if profile
                    else scope
                )

                if len(profile_centers) == 1:
                    center = profile_centers[0]
                else:
                    attitre_centers = profile_centers.filtered(
                        lambda c: c.bc_user_profile == profile
                    )
                    if len(attitre_centers) == 1:
                        center = attitre_centers[0]
                    else:
                        raise UserError(
                            _("Centre non unique pour le poste %s")
                            % (poste.display_name,)
                        )

        if not center:
            return {}

        key = f"{center.id},{poste.id}"
        return {key: 100}
