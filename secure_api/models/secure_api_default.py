# -*- coding: utf-8 -*-
from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class SecureAPIDefault(models.Model):
    _name = "secure.api.default"
    _description = "Secure API Default Field Values"

    name = fields.Char(string="Technical Name", related="field_id.name")
    model_id = fields.Many2one("ir.model", string="Model", required=True, ondelete="cascade")
    field_id = fields.Many2one("ir.model.fields", string="Field", required=True, ondelete="cascade")
    field_type = fields.Selection(string="Field Type", related="field_id.ttype")
    value = fields.Text("Value", required=True, help="Value type is converted with field type")
    secure_api_id = fields.Many2one("secure.api", string="Secure API", required=True, ondelete="cascade")
