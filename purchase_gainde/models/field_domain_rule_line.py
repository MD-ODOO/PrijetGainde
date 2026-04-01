from odoo import models, fields


class FieldDomainRuleLine(models.Model):
    """Stub technique pour le modèle manquant ``field.domain.rule.line``.

    Certains écrans/accessoires du module ``access_users_manager``
    référencent ce modèle. Il n'est pas présent dans l'instance, ce qui
    provoque un ``KeyError`` dans le registre Odoo. Ce stub en
    fournit une implémentation minimale, suffisante pour éviter
    l'erreur, sans modifier le module d'origine.
    """

    _name = "field.domain.rule.line"
    _description = "Field Domain Rule Line (stub)"

    model_id = fields.Many2one("ir.model", string="Model")
    # Champ générique utilisé par certains hooks externes (ex: dynamic_domain_builder)
    # qui recherchent sur ``field_name.relation``.
    field_name = fields.Many2one("ir.model.fields", string="Field Name")
    # Lien vers la règle parente, utilisé dans des domaines du type
    # ``('rule_id.active', '=', True)``.
    rule_id = fields.Many2one("field.domain.rule", string="Rule")
    # Ancien champ interne éventuel, conservé pour compatibilité si déjà utilisé ailleurs.
    field_id = fields.Many2one("ir.model.fields", string="Field")
    domain = fields.Char(string="Domain")
