from odoo import models


class ResPartnerNameGetPatch(models.Model):
    _inherit = "res.partner"

    def name_get(self):
        """Compat Odoo 18: name_get n'existe plus nativement.

        Le module partner_tier_account appelle encore partners.name_get() dans
        name_search. On fournit une implémentation sûre basée sur display_name.
        """
        # Contexte utilisé par partner_tier_account pour ne pas préfixer.
        if self.env.context.get("skip_tier_account_prefix"):
            return [(partner.id, partner.display_name or partner.name or "") for partner in self]

        result = []
        for partner in self:
            display = partner.display_name or partner.name or ""
            tier = (getattr(partner, "tier_account", "") or "").strip()
            if tier and not display.startswith(tier):
                display = f"{tier} - {display}"
            result.append((partner.id, display))
        return result
