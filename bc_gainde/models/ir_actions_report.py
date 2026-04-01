from odoo import api, models, _
from odoo.exceptions import UserError


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _gainde_user_has_profile_type(self, user, profile_type):
        """Vérifie si l'utilisateur a un profil donné (ex: 'ra')."""
        user = user.sudo()
        
        # Check if user has direct profile relationship
        if "access_profile_ids" in user._fields and user.access_profile_ids:
            if profile_type in user.access_profile_ids.mapped("profile_type"):
                return True
        
        # Check if user is in profile lines
        if "user.profile.lines" in self.env:
            ProfileLine = self.env["user.profile.lines"].sudo()
            domain = [("access_user_id", "=", user.id)]
            if "active" in ProfileLine._fields:
                domain.append(("active", "=", True))
            if "access_is_enabled" in ProfileLine._fields:
                domain.append(("access_is_enabled", "=", True))
            lines = ProfileLine.search(domain)
            profiles = lines.mapped("access_profile_id")
            if profiles and profile_type in profiles.mapped("profile_type"):
                return True
        
        # Check if user is in profile's access_user_ids
        if "user.profiles" in self.env:
            Profile = self.env["user.profiles"].sudo()
            profiles = Profile.search([("profile_type", "=", profile_type)])
            for profile in profiles:
                if user in profile.access_user_ids:
                    return True
        
        return False
    
    def _user_has_ra_profile(self, user):
        """Vérifie si l'utilisateur a le profil 'ra'."""
        return self._gainde_user_has_profile_type(user, "ra")
    
    def _user_has_allowed_profile(self, user):
        """Vérifie si l'utilisateur a le profil 'ra'."""
        return self._gainde_user_has_profile_type(user, "ra")

    @api.model
    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        # Block printing for this specific report
        if report_ref == "bc_gainde.gainde_report" and res_ids:
            if not any([
                self.env.is_superuser(),
                self._user_has_allowed_profile(self.env.user)
            ]):
                raise UserError(_("Seuls les superutilisateurs ou les profils autorisés peuvent imprimer ce rapport."))

            orders = self.env["purchase.order"].browse(res_ids)

            # Check partner approval
            not_approved_partner = orders.filtered(
                lambda o: o.partner_id.approval_state != "approved"
            )
            if not_approved_partner:
                raise UserError(
                    _("Impossible d'imprimer : le fournisseur doit être approuvé.")
                )

            # Check product approval on order lines
            not_approved_products = orders.mapped("order_line").filtered(
                lambda l: l.product_id and l.product_id.approval_state != "approved"
            )
            if not_approved_products:
                raise UserError(
                    _("Impossible d'imprimer : tous les produits doivent être approuvés.")
                )

        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)