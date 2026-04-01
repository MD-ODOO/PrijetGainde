# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SecureApiTag(models.Model):
    _name = "secure.api.tag"
    _description = "Secure API Tag"

    name = fields.Char("Tag Name", required=True)
    color = fields.Integer("Color Index")
    active = fields.Boolean(default=True, help="Set active to false to hide the Secure Tag without removing it.")
    sequence = fields.Integer(help="Gives the sequence order when displaying a list of tags.")

