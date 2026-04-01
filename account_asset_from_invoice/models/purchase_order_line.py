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
        if template.type != "combo" or not template.combo_ids:
            return template.type

        combo_types = template.combo_ids.mapped("product_tmpl_id.type")
        if "service" in combo_types:
            return "service"
        return "consu"
    def _gainde_get_applicable_tax(self, partner, product, company, type_tax_use):
        if not partner or not product or not company:
            return self.env["account.tax"]

        product_type = self._gainde_get_effective_product_type(product)
        if product_type != "service":
            return self.env["account.tax"]

        is_national = partner.country_id and partner.country_id.code == "SN"
        if not is_national:
            return self._gainde_get_tax_by_name("20%", type_tax_use, company)

        cofi = (partner.cofi or "").strip()
        if not cofi:
            return self.env["account.tax"]

        first = cofi[0]


        if first == "0":
            return self.env["account.tax"]
        if first == "1":
            name = "5%s" if partner.is_supplier_support_vrs else "5%t"
            return self._gainde_get_tax_by_name(name, type_tax_use, company)
        if first == "2":
            return self._gainde_get_tax_by_name("18%", type_tax_use, company)

        return self.env["account.tax"]

    # def _gainde_get_applicable_tax(self, partner, product, company, type_tax_use):
    #     # TODO: implement logic or remove this method
    #     #_gainde_get_tax_by_name = self._gainde_get_tax_by_name()
       
    #     product_type = self._gainde_get_effective_product_type(product)

    #     return self.env["account.tax"].search([])

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
            # Clear taxes when no rule tax applies.
            if not taxes:
                if line.taxes_id:
                    line.with_context(skip_gainde_tax=True).taxes_id = [(6, 0, [])]
                continue
            if set(line.taxes_id.ids) == set(taxes.ids):
                continue
            line.with_context(skip_gainde_tax=True).taxes_id = [(6, 0, taxes.ids)]


    @api.onchange(
        "product_id",
        "order_id.partner_id",
        "order_id.partner_id.cofi",
        "order_id.partner_id.country_id",
        "order_id.partner_id.is_supplier_support_vrs",
        "product_id.product_tmpl_id.type",
        "product_id.product_tmpl_id.combo_ids",
    )
    def _onchange_gainde_tax_rules(self):
        self._gainde_apply_tax_rules()

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line, vals in zip(lines, vals_list):
            # Respect manual taxes selected in the form payload.
            if "taxes_id" in vals:
                continue
            line._gainde_apply_tax_rules()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("skip_gainde_tax"):
            return res
        # Recompute only when tax-driving fields change, and keep explicit user taxes.
        trigger_fields = {"product_id", "company_id", "order_id"}
        if "taxes_id" not in vals and trigger_fields.intersection(vals.keys()):
            self._gainde_apply_tax_rules()
        return res
