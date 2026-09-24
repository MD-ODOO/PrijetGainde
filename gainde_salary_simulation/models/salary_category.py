# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class GaindeSalaryCategory(models.Model):
    _name = 'gainde.salary.category'
    _description = 'Catégorie socio-professionnelle - Simulation de salaire'
    _order = 'sequence, code, id'

    name = fields.Char(string='Libellé', required=True)
    code = fields.Char(string='Code', required=True)
    base_salary = fields.Monetary(
        string='Salaire de base',
        currency_field='currency_id',
        required=True,
        default=0.0,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    currency_id = fields.Many2one(
        'res.currency',
        string='Devise',
        default=lambda self: self.env.company.currency_id,
        required=True,
        readonly=True,
    )
    note = fields.Text(string='Note')

    _sql_constraints = [
        ('code_unique', 'unique(code)', _('Le code de la catégorie doit être unique.')),
    ]

    @api.constrains('base_salary')
    def _check_base_salary(self):
        for record in self:
            if record.base_salary < 0:
                raise ValidationError(_('Le salaire de base ne peut pas être négatif.'))
