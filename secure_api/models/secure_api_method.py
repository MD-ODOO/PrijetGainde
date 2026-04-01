# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class SecureAPIMethod(models.Model):
    _name = "secure.api.method"
    _description = "Secure API Method"

    name = fields.Char(string="Name", required=True)

