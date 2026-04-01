from odoo import models, fields


class HrEmployeeRateProfile(models.Model):
    _name = 'hr.employee.rate.profile'
    _description = "Profil de coût horaire par expérience / autonomie"

    name = fields.Char(string="Nom du profil", required=True)
    min_years = fields.Integer(string="Années min", default=0)
    max_years = fields.Integer(string="Années max", default=99)
    hourly_rate = fields.Float(string="Coût horaire", required=True, default=400.0)

    _sql_constraints = [
        ('name_unique', 'unique(name)', "Ce nom de profil existe déjà !")
    ]
