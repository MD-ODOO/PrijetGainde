from odoo import models, fields


class AssetLocalisation(models.Model):
    _name = "asset.localisation"
    _description = "Localisation des actifs"

    name = fields.Char(string="Nom", required=True)
    adresse = fields.Char(string="Adresse")

