from odoo import models
from odoo import api, fields, models, _


class GaindeTaxRuleMixin(models.AbstractModel):
    _name = "gainde.tax.rule.mixin"
    _description = "Gainde Tax Rule Mixin"
   
    
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