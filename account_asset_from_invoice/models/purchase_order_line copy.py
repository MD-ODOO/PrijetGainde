from odoo import api, models


class PurchasePartnerOrderLine(models.Model):
    _inherit = "purchase.order.line"
   
   
    def _gainde_get_tax_by_name(self, name, type_tax_use, company):
        return self.env["account.tax"].search(
            [
                ("name", "=", name),
                ("type_tax_use", "=", type_tax_use),
                ("company_id", "in", [company.id, False]),
                ("active", "=", True),
            ],
            limit=1,
        )

    def _gainde_get_effective_product_type(self, product):
        template = product.product_tmpl_id
        if not template:
            return False
        if template.product_type != "combo" or not template.combo_ids:
            return template.product_type

        combo_types = template.combo_ids.mapped("product_tmpl_id.product_type")
        # Assumption: if any component is service, treat the combo as service
        if "service" in combo_types:
            return "service"
        return "consu"

    def _gainde_get_applicable_tax(self, partner, product, company, type_tax_use):
    def _gainde_apply_tax_rules(self):
        if self.env.context.get("skip_gainde_tax"):
            return
        for line in self:
            if line.display_type:
                continue
            partner = line.order_id.partner_id
            product = line.product_id
            company = line.order_id.company_id
            if not partner or not product or not company:
                continue
            taxes = line._gainde_get_applicable_tax(
                partner=partner,
                product=product,
                company=company,
                type_tax_use="purchase",
            )
            line.with_context(skip_gainde_tax=True).taxes_id = taxes

    @api.onchange(
        "product_id",
        "order_id.partner_id",
        "order_id.partner_id.cofi",
        "order_id.partner_id.country_id",
        "order_id.partner_id.is_supplier_support_vrs",
        "product_id.product_tmpl_id.product_type",
        "product_id.product_tmpl_id.combo_ids",
    )
    def _onchange_gainde_tax_rules(self):
        self._gainde_apply_tax_rules()

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._gainde_apply_tax_rules()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_gainde_tax"):
            self._gainde_apply_tax_rules()
        return res