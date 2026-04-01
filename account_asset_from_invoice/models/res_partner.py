from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"
    
    def _default_is_supplier(self):
        ctx = self.env.context
        if "default_is_supplier" in ctx:
            return bool(ctx.get("default_is_supplier"))
        if ctx.get("default_supplier_rank"):
            return True
        return False

    def _default_is_customer(self):
        ctx = self.env.context
        if "default_is_customer" in ctx:
            return bool(ctx.get("default_is_customer"))
        if ctx.get("default_customer_rank"):
            return True
        return False

    cin = fields.Char(string="CNI")
    cofi = fields.Char(string="COFI")
    is_supplier_support_vrs = fields.Boolean(string="Gainde Supporte BRS?", default=True)
    is_supplier = fields.Boolean(string="Est fournisseur", default=_default_is_supplier)
    is_customer = fields.Boolean(string="Est client", default=_default_is_customer)
    is_cofi_prefix_1 = fields.Boolean(
        string="COFI starts with 1",
        compute="_compute_is_cofi_prefix_1",
    )

    @api.depends("cofi")
    def _compute_is_cofi_prefix_1(self):
        for partner in self:
            cofi = (partner.cofi or "").strip()
            partner.is_cofi_prefix_1 = bool(cofi) and cofi[0] == "1"

    @api.constrains("cofi")
    def _check_cofi_format(self):
        for partner in self:
            if not partner.cofi:
                continue
            cofi = partner.cofi.strip()
            if len(cofi) < 3:
                raise UserError(_("COFI must have at least 3 characters."))
            first, second, third = cofi[0], cofi[1], cofi[2]
            if first not in ("0", "1", "2"):
                raise UserError(_("COFI first character must be 0, 1, or 2."))
            if not second.isalpha():
                raise UserError (_("COFI second character must be a letter."))
            if not third.isdigit():
                raise UserError(_("COFI third character must be a number."))