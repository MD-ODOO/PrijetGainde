from odoo import fields, models


class FormJuridique(models.Model):
    _name = "form.juridique"
    _description = "Forme Juridique"
    _rec_name = "name"

    name = fields.Char(string="Nom", required=True)
    description = fields.Text(string="Description")
