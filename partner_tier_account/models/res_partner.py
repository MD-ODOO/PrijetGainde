from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    tier_account = fields.Char(
        string='Compte Tiers',
        copy=False,
        help='Identifiant unique du compte tiers pour ce partenaire'
    )

    _sql_constraints = [
        ('tier_account_unique', 'UNIQUE(tier_account)', 
         "Ce compte de tiers appartient déjà à un partenaire!")
    ]

    @api.constrains('tier_account')
    def _check_tier_account_unique(self):
        for record in self:
            if record.tier_account:
                existing = self.search([
                    ('tier_account', '=', record.tier_account),
                    ('id', '!=', record.id)
                ], limit=1)
                if existing:
                    raise ValidationError(
                        _('Ce compte de tiers « %s » appartient déjà à quelqu\'un "%s".') 
                        % (record.tier_account, existing.display_name)
                    )

    def name_get(self):
        res = super().name_get()
        if self.env.context.get('skip_tier_account_prefix'):
            return res

        tier_by_id = {
            partner.id: (partner.tier_account or '').strip()
            for partner in self
        }

        updated = []
        for partner_id, display_name in res:
            tier_account = tier_by_id.get(partner_id)
            if tier_account and not (display_name or '').startswith(tier_account):
                updated.append((partner_id, f"{tier_account} - {display_name}"))
            else:
                updated.append((partner_id, display_name))
        return updated

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = list(args or [])
        if not name:
            return super().name_search(name=name, args=args, operator=operator, limit=limit)

        partners = self.search([('tier_account', operator, name)] + args, limit=limit)
        results = partners.name_get() if partners else []
        if limit and len(results) >= limit:
            return results[:limit]

        remaining = (limit - len(results)) if limit else 0
        if remaining == 0 and limit:
            return results

        # Compléter avec la recherche standard (nom, ref, email, etc.)
        extra = super().name_search(
            name=name,
            args=args + [('id', 'not in', partners.ids)],
            operator=operator,
            limit=remaining or limit,
        )
        return results + (extra or [])
