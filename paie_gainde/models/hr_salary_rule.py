# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)

class SalaryRuleInherit(models.Model):
    """Héritage pour la règle de salaire"""
    _inherit = 'hr.salary.rule'
    _order = 'sequence'

    # Exemple de champ supplémentaire
    is_special_rule = fields.Boolean(string="Règle spéciale")
