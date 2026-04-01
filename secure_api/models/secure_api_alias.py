# -*- coding: utf-8 -*-
from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class SecureAPIAlias(models.Model):
    _name = "secure.api.alias"
    _description = "Secure API Field Alias"

    name = fields.Char(string="Technical Name", related="field_id.name")
    model_id = fields.Many2one("ir.model", string="Model", required=True, ondelete="cascade")
    field_id = fields.Many2one("ir.model.fields", string="Field", required=True, ondelete="cascade")
    field_name = fields.Char(string="Field Name", related="field_id.name")
    alias = fields.Char(string="Alias", required=True, help="The alias name to use for this field in API responses and requests")
    secure_api_id = fields.Many2one("secure.api", string="Secure API", required=True, ondelete="cascade")

