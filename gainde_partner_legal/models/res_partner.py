from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    form_juridique_id = fields.Many2one(
        "form.juridique",
        string="Forme juridique",
    )
    rccm = fields.Char(string="RCCM")

    @api.model_create_multi
    def create(self, vals_list):
        new_vals_list = []
        for vals in vals_list:
            vals = dict(vals)
            if vals.get("company_type") == "person":
                vals["is_company"] = False
            elif vals.get("company_type") == "company":
                vals["is_company"] = True
            new_vals_list.append(vals)
        return super().create(new_vals_list)

    def write(self, vals):
        vals = dict(vals)
        if vals.get("company_type") == "person":
            vals["is_company"] = False
        elif vals.get("company_type") == "company":
            vals["is_company"] = True
        return super().write(vals)

    def _gainde_is_supplier_or_customer(self):
        self.ensure_one()

        if "is_supplier" in self._fields or "is_customer" in self._fields:
            return bool(getattr(self, "is_supplier", False) or getattr(self, "is_customer", False))

        supplier_rank = getattr(self, "supplier_rank", 0) or 0
        customer_rank = getattr(self, "customer_rank", 0) or 0
        return supplier_rank > 0 or customer_rank > 0

    def _gainde_get_optional_char(self, field_name):
        self.ensure_one()
        if field_name not in self._fields:
            return ""
        return (getattr(self, field_name) or "").strip()

    # @api.constrains("company_type", "vat", "rccm", "supplier_rank", "customer_rank")
    # def _check_partner_required_identifiers(self):
    #     for partner in self:
    #         if not partner._gainde_is_supplier_or_customer():
    #             continue

    #         if partner.company_type == "company":
    #             if not (partner.vat or "").strip():
    #                 raise UserError(_("Le champ NINEA/VAT est obligatoire pour une société."))

    #             cofi = partner._gainde_get_optional_char("cofi")
    #             if "cofi" in partner._fields and not cofi:
    #                 raise UserError(_("Le champ COFI est obligatoire pour une société."))

    #             # if not (partner.rccm or "").strip():
    #             #     raise UserError(_("Le champ RCCM est obligatoire pour une société."))
    #         else:
    #             cin = partner._gainde_get_optional_char("cin")
    #             if "cin" in partner._fields and not cin:
    #                 raise UserError(_("Le champ CIN est obligatoire pour une personne."))
