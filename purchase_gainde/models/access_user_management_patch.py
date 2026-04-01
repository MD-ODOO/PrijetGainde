from odoo import models
from odoo.http import request


class UserManagement(models.Model):
    _inherit = "user.management"

    def access_search_action_button(self, model):
        """Version defensive: ne plante pas si le cookie cids est absent/malforme."""
        hide_element = []

        cids_cookie = False
        if request and request.httprequest:
            cids_cookie = request.httprequest.cookies.get("cids")

        company_ids = []
        if cids_cookie:
            for part in str(cids_cookie).split("-"):
                part = part.strip()
                if part.isdigit():
                    company_ids.append(int(part))

        if not company_ids:
            company_ids = [self.env.company.id]

        is_archive_hide = self.env["model.access"].sudo().search(
            [
                ("access_model_id.model", "=", model),
                ("access_user_management_id.active", "=", True),
                ("access_user_management_id.access_company_ids", "in", company_ids),
                ("access_user_management_id.access_user_ids", "in", self.env.user.id),
                ("access_hide_archive_unarchive", "=", True),
            ],
            limit=1,
        )
        is_export_hide = self.env["model.access"].sudo().search(
            [
                ("access_model_id.model", "=", model),
                ("access_user_management_id.active", "=", True),
                ("access_user_management_id.access_company_ids", "in", company_ids),
                ("access_user_management_id.access_user_ids", "in", self.env.user.id),
                ("access_hide_export", "=", True),
            ],
            limit=1,
        )

        if is_archive_hide:
            hide_element += ["archive", "unarchive"]
        if is_export_hide:
            hide_element += ["export"]

        return hide_element
