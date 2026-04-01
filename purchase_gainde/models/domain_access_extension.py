from odoo import fields, models
from odoo.osv import expression
from odoo.tools.safe_eval import safe_eval
from odoo.http import request


class PurchaseGaindeDomainAccess(models.Model):
    _inherit = "domain.access"

    # On enlève la restriction d'origine qui ne permettait de choisir
    # qu'un sous-ensemble de modèles (access_profile_domain_model).
    # Ici, l'utilisateur est libre de choisir n'importe quel modèle.
    access_model_id = fields.Many2one(
        "ir.model",
        string="Model",
        domain=[],
    )


class PurchaseGaindeIrRule(models.Model):
    _inherit = "ir.rule"

    def _compute_domain(self, model_name, mode="read"):
        """Affinage du calcul de domaine pour les règles custom Gainde.

        Problème fonctionnel : lorsqu'un utilisateur change de profil,
        il garde parfois le domaine du premier profil car la règle
        custom reste appliquée alors que, fonctionnellement, le pack
        (user.management) ne devrait plus le concerner.

        On garde la logique d'access_users_manager, mais on renforce
        la condition pour les règles ``custom`` en vérifiant que
        l'utilisateur courant a *encore* un profil actif parmi ceux du
        pack (via ``gainde_get_current_profiles``).
        """
        # Domaines hérités (via _inherits) et domaines custom Gainde
        global_domains = []  # list of domains (hérités + éventuellement globaux non custom)
        parent_domains = []  # uniquement les domaines issus des modèles parents
        custom_domains = []  # domaines des règles custom Gainde applicables à l'utilisateur

        # add rules for parent models
        for parent_model_name, parent_field_name in self.env[model_name]._inherits.items():
            if domain := self._compute_domain(parent_model_name, mode):
                parent_domain = [(parent_field_name, "any", domain)]
                parent_domains.append(parent_domain)
                global_domains.append(parent_domain)

        rules = self._get_rules(model_name, mode=mode)
        if not rules:
            return expression.AND(global_domains) if global_domains else []

        # browse user and rules as SUPERUSER_ID to avoid access errors!
        eval_context = self._eval_context()
        user_groups = self.env.user.groups_id
        group_domains = []  # list of domains

        env_user = self.env.user

        # Indique si au moins une règle custom Gainde s'applique pour ce modèle
        # et cet utilisateur. Dans ce cas, on laisse ces règles piloter le
        # domaine et on ignore les autres règles de groupes standard.
        has_custom_gainde_rule = False

        for rule in rules.sudo():
            # evaluate the domain for the current user
            dom = safe_eval(rule.domain_force, eval_context) if rule.domain_force else []
            dom = expression.normalize_domain(dom)
            custom_global_domain = False

            if rule.custom:
                profile_mgmt = rule.access_domain_access_id.access_user_management_id
                if profile_mgmt:
                    # Companies courantes (comme dans access_users_manager)
                    cids = request.httprequest.cookies.get("cids") if request and request.httprequest else None
                    if cids:
                        company_ids = [int(x) for x in cids.split("-")]
                    else:
                        company_ids = env_user.company_ids.ids or []

                    # On applique la règle custom uniquement si :
                    #  - le pack est actif
                    #  - l'utilisateur fait partie des utilisateurs du pack
                    #    (access_user_ids déjà calculé par access_users_manager)
                    #  - et la société courante fait partie des sociétés du pack
                    if (
                        profile_mgmt.active
                        and env_user in profile_mgmt.access_user_ids
                    ):
                        for company_id in company_ids:
                            if company_id in profile_mgmt.access_company_ids.ids:
                                custom_global_domain = True
                                has_custom_gainde_rule = True
                                break

            if not rule.groups and custom_global_domain:
                # Domaine global custom pour ce modèle / pack
                global_domains.append(dom)
                custom_domains.append(dom)
            elif rule.groups & user_groups and not rule.custom:
                group_domains.append(dom)

        # Si au moins une règle custom Gainde s'applique, on laisse ces
        # règles (et les domaines hérités) piloter entièrement le domaine,
        # sans ajouter les autres règles de groupes standards.
        #
        # IMPORTANT : lorsqu'il y a plusieurs Domain Access custom actifs
        # (plusieurs packs / plusieurs profils), on veut l'union de leurs
        # enregistrements, pas l'intersection. On combine donc :
        #   (domaines parents) AND (DOM1 OR DOM2 OR ...)
        if has_custom_gainde_rule:
            domains_to_and = []
            # Toujours appliquer les contraintes des modèles parents
            if parent_domains:
                domains_to_and.extend(parent_domains)

            # Union de tous les domaines custom applicables
            if custom_domains:
                if len(custom_domains) == 1:
                    custom_union = custom_domains[0]
                else:
                    custom_union = expression.OR(custom_domains)
                domains_to_and.append(custom_union)

            return expression.AND(domains_to_and) if domains_to_and else []

        # Sinon, on combine domaines globaux standard et domaines par groupes
        if not group_domains:
            return expression.AND(global_domains)
        return expression.AND(global_domains + [expression.OR(group_domains)])

