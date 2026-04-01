# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class IrModelFields(models.Model):
    _name = "ir.model.fields"
    _inherit = "ir.model.fields"

    def name_get(self):
        result = []
        for field in self:
            name = "%s (%s)" % (field.field_description, field.name)
            result.append((field.id, name))
        return result

