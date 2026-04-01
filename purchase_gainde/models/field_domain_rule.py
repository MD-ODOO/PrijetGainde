from odoo import models, fields


class FieldDomainRule(models.Model):
    """Stub minimal pour le modèle manquant ``field.domain.rule``.

    Utilisé comme comodel de ``field.domain.rule.line.rule_id`` pour
    satisfaire les domaines de type ``('rule_id.active', '=', True)``.
    """

    _name = "field.domain.rule"
    _description = "Field Domain Rule (stub)"

    name = fields.Char(string="Name")
    # Propriétaire / utilisateur de la règle, utilisé dans certains domaines
    # de type ('user_id', '=', uid).
    user_id = fields.Many2one("res.users", string="User")
    active = fields.Boolean(string="Active", default=True)
