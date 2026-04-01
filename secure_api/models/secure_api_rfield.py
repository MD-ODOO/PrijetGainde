# -*- coding: utf-8 -*-
from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class SecureAPIRfield(models.Model):
    _name = "secure.api.rfield"
    _description = "Secure API Related Model Field"

    name = fields.Char(string="Technical Name", related="model_id.model")
    model_id = fields.Many2one("ir.model", string="Model", required=True, ondelete="cascade")
    field_ids = fields.Many2many("ir.model.fields", "api_rfield_rel", string="Fields", required=True)
    secure_api_id = fields.Many2one("secure.api", string="Secure API", required=True, ondelete="cascade")
