# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta
from dateutil import relativedelta
import logging

_logger = logging.getLogger(__name__)
DATE_FORMAT = '%Y-%m-%d'
FRENCH_DATE_FORMAT = '%d/%m/%Y'

class ResCompany(models.Model):
    _inherit = "res.company"

    Cfce = fields.Many2one('hr.employee','Président directeur général')
   


    