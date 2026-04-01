# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
from odoo.osv import expression
from odoo.tools.safe_eval import safe_eval
from odoo.http import request

class KsDomainAccess(models.Model):
    _name = 'domain.access'
    _description = 'Domain Access'

    access_model_id = fields.Many2one('ir.model', string='Model', domain="[('id', 'in', access_profile_domain_model )]")
    access_model_name = fields.Char(related='access_model_id.model', string='Model Name')
    access_create_access = fields.Boolean(string='Create')
    access_read_access = fields.Boolean(string='Read', default=True)
    access_write_access = fields.Boolean(string='Write')
    access_delete_access = fields.Boolean(string='Delete')
    access_apply_domain = fields.Boolean(string='Apply Domain')
    access_domain = fields.Text(string="Domain", default='[]')
    access_user_management_id = fields.Many2one('user.management', string='Management Rule')
    access_rule_id = fields.Many2one('ir.rule', string='Rule')
    access_profile_domain_model = fields.Many2many('ir.model', related='access_user_management_id.access_profile_domain_model')

    @api.model_create_multi
    def create(self, vals_list):
        res = super(KsDomainAccess, self).create(vals_list)
        # Create record rule for the domain access.
        res.access_create_domain_access()
        return res

    def write(self, vals):
        """Update record rule for the domain access."""
        res = super(KsDomainAccess, self).write(vals)
        for model in self:
            data = {
                'name': model.access_model_id.name + ' Custom domain',
                'model_id': model.access_model_id.id,
                'domain_force': model.access_domain,
                'perm_create': model.access_create_access,
                'perm_write': model.access_write_access,
                'perm_read': model.access_read_access,
                'perm_unlink': model.access_delete_access,
            }
            model.access_rule_id.sudo().write(data)
        return res

    def unlink(self, rule=False):
        """Unlink record rule for the domain access."""
        for model in self:
            if not rule:
                model.access_rule_id.sudo().unlink()
        res = super(KsDomainAccess, self).unlink()
        return res

    def access_create_domain_access(self):
        for model in self:
            data = {
                'name': model.access_model_id.name + self.access_user_management_id.name,
                'model_id': model.access_model_id.id,
                'domain_force': model.access_domain,
                'perm_create': model.access_create_access,
                'perm_write': model.access_write_access,
                'perm_read': model.access_read_access,
                'perm_unlink': model.access_delete_access,
                # 'groups': model.access_create_group(),
                'access_domain_access_id': self.id,
                'custom': True

            }
            rule_id = self.env['ir.rule'].sudo().create(data)
            model.access_rule_id = rule_id.id

    def access_create_group(self):
        user_ids = self.access_user_management_id.access_user_ids
        group_values = {
            'name': self.access_user_management_id.name + ' ' + self.access_model_id.name,
            'users': user_ids,
            'custom': True,
            'comment': 'This is a new group created for Domain Access',
        }
        group_id = self.env['res.groups'].sudo().create(group_values)
        return group_id


class IrRule(models.Model):
    _inherit = "ir.rule"

    access_domain_access_id = fields.Many2one('domain.access')
    custom = fields.Boolean(string='Custom Rule')

    def unlink(self):
        self.access_domain_access_id.unlink(rule=True)
        group = self.groups
        res = super(IrRule, self).unlink()
        group.sudo().unlink()
        return res

    @api.model
    def _compute_domain(self, model_name, mode="read"):
        """Compute the effective domain for record rules.

        Adapté pour Domain Access afin que, lorsqu'un utilisateur a
        plusieurs packs/profils (plusieurs règles custom), les domaines
        correspondants soient combinés en **OU** entre eux, tout en
        restant en **ET** avec les domaines hérités via ``_inherits``.
        """

        # Domaines hérités (via _inherits) et domaines custom
        global_domains = []  # domaines "globaux" standards
        parent_domains = []  # uniquement ceux issus des modèles parents
        custom_domains = []  # domaines des règles custom Domain Access

        # add rules for parent models
        for parent_model_name, parent_field_name in self.env[model_name]._inherits.items():
            if domain := self._compute_domain(parent_model_name, mode):
                parent_domain = [(parent_field_name, 'any', domain)]
                parent_domains.append(parent_domain)
                global_domains.append(parent_domain)

        rules = self._get_rules(model_name, mode=mode)
        if not rules:
            return expression.AND(global_domains) if global_domains else []

        # browse user and rules as SUPERUSER_ID to avoid access errors!
        eval_context = self._eval_context()
        user_groups = self.env.user.groups_id
        group_domains = []  # list of domains (règles non custom avec groupes)
        for rule in rules.sudo():
            # evaluate the domain for the current user
            dom = safe_eval(rule.domain_force, eval_context) if rule.domain_force else []
            dom = expression.normalize_domain(dom)
            custom_global_domain = False
            # Evaluate custom group as a global group
            if rule.custom:
                profile = rule.access_domain_access_id.access_user_management_id
                env_user = self.env.user
                cids = request.httprequest.cookies.get('cids')
                if cids:
                    company_ids = [int(x) for x in cids.split('-')]
                    for company_id in company_ids:
                        if profile.active and env_user.id in profile.access_user_ids.ids and company_id in profile.access_company_ids.ids:
                            custom_global_domain = True

            if not rule.groups and custom_global_domain:
                # Domaine global custom pour ce modèle / pack
                custom_domains.append(dom)
            elif rule.groups & user_groups and not rule.custom:
                group_domains.append(dom)

        # S'il y a des domaines custom (Domain Access), on veut :
        #   (domaines parents) AND (DOM_custom1 OR DOM_custom2 OR ...) AND OR(group_domains)
        if custom_domains:
            # Union logique de tous les domaines custom applicables
            if len(custom_domains) == 1:
                custom_union = custom_domains[0]
            else:
                custom_union = expression.OR(custom_domains)

            domains_to_and = []
            if parent_domains:
                domains_to_and.extend(parent_domains)

            domains_to_and.append(custom_union)

            # Ajouter les domaines par groupes standard le cas échéant
            if group_domains:
                domains_to_and.append(expression.OR(group_domains))

            return expression.AND(domains_to_and)

        # Sinon, on conserve le comportement standard :
        # combine global domains and group domains
        if not group_domains:
            return expression.AND(global_domains)
        return expression.AND(global_domains + [expression.OR(group_domains)])
        # for rule in rules.sudo():
        #     # evaluate the domain for the current user
        #     dom = safe_eval(rule.domain_force, eval_context) if rule.domain_force else []
        #     dom = expression.normalize_domain(dom)
        #     custom_global_domain = False
        #     # Evaluate custom group as a global group ( Word as AND condition)
        #     if rule.custom:
        #         profile = rule.access_domain_access_id.access_user_management_id
        #         env_user = self.env.user
        #         company_ids = self._context.get('allowed_company_ids')
        #         if company_ids:
        #             for company_id in company_ids :
        #                 if profile.active and env_user.id in profile.access_user_ids.ids and company_id in profile.access_company_ids.ids:
        #                     custom_global_domain = True
        #     if not rule.groups or custom_global_domain:
        #         global_domains.append(dom)
        #     elif rule.groups & user_groups and not rule.custom:
        #         group_domains.append(dom)
        #
        # # combine global domains and group domains
        # if not group_domains:
        #     return expression.AND(global_domains)
        # return expression.AND(global_domains + [expression.OR(group_domains)])
