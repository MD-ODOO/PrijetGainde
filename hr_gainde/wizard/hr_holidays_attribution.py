# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime
import logging

log = logging.getLogger(__name__)
DATE_FORMAT = '%Y-%m-%d'
FRENCH_DATE_FORMAT = '%d/%m/%Y'

class HrHolidaysAttribution(models.TransientModel):
    _name = "nrt.hr_holidays.attribution"
    _description = "Attribution manuelle de congés"

    name = fields.Char(string="Description", required=True)
    date_start = fields.Date(string="Date début", required=True)
    date_stop = fields.Date(string="Date fin", required=True)
    number_of_days = fields.Float(string="Nombre de jours", required=True)
    leave_id = fields.Many2one('hr.leave.type', string="Type de congé", required=True)

    def attribute(self):
        """Attribue le nombre de jours à tous les employés."""
        employees = self.env['hr.employee'].search([])
        for employee in employees:
            holiday = self.env['hr.leave'].create({
                'employee_id': employee.id,
                'holiday_status_id': self.leave_id.id,
                'number_of_days': self.number_of_days,
                'request_date_from': self.date_start,
                'request_date_to': self.date_stop,
                'name': self.name,
                'state': 'validate',  # direct validation
                'holiday_type': 'employee',  # type de congé
            })
            log.info(f"Congé attribué à {employee.name}: {self.number_of_days} jour(s)")
