# -*- coding: utf-8 -*-
from odoo import models, api, fields
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class ResCompany(models.Model):
    _inherit = 'res.company'

   
    cfce = fields.Boolean(
        string="CFCE",
    )

    work_accident = fields.Float(
        string="Accident de Travail")


    @api.model
    def _trigger_legal_holidays_tasks(self):
        today = datetime.today().date()
        first_day_in_month = today.replace(day=1)
        last_day_in_month = (first_day_in_month + relativedelta.relativedelta(months=1, days=-1))

        month_before = first_day_in_month.month - 1 if first_day_in_month.month > 1 else 12
        year_before = first_day_in_month.year if month_before != 12 else first_day_in_month.year -1
        first_day_month_before = datetime(year_before, month_before, 1).date()
        last_day_month_before = first_day_in_month - timedelta(days=1)

        leave_type = self.env['hr.leave.type'].search([('is_legal_leave', '=', True)], limit=1)
        if not leave_type:
            _logger.warning("Aucun type de congé légal trouvé.")
            return

        for employee in self.env['hr.employee'].search([]):
            company = self
            if not company.active_attribution:
                continue

            # Congés du mois précédent
            last_allocation = self.env['hr.leave'].search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id', '=', leave_type.id),
                ('holiday_type', '=', 'employee'),
            ], limit=1, order='date_to desc')

            if not last_allocation:
                leave = self.env['hr.leave'].create({
                    'employee_id': employee.id,
                    'holiday_status_id': leave_type.id,
                    'number_of_days': company.number_days_holidays_allocation,
                    'name': f"Congé légal pour la période du {first_day_month_before.strftime(FRENCH_DATE_FORMAT)} au {last_day_month_before.strftime(FRENCH_DATE_FORMAT)}",
                    'request_date_from': first_day_month_before,
                    'request_date_to': last_day_month_before,
                    'state': 'confirm',
                    'holiday_type': 'employee'
                })
                leave.action_validate_leave()

            # Congés du mois en cours à la fin du mois
            if today == last_day_in_month:
                last_allocation = self.env['hr.leave'].search([
                    ('employee_id', '=', employee.id),
                    ('holiday_status_id', '=', leave_type.id),
                    ('holiday_type', '=', 'employee'),
                ], limit=1, order='date_to desc')
                if not last_allocation:
                    leave = self.env['hr.leave'].create({
                        'employee_id': employee.id,
                        'holiday_status_id': leave_type.id,
                        'number_of_days': company.number_days_holidays_allocation,
                        'name': f"Congé légal pour la période du {first_day_in_month.strftime(FRENCH_DATE_FORMAT)} au {last_day_in_month.strftime(FRENCH_DATE_FORMAT)}",
                        'request_date_from': first_day_in_month,
                        'request_date_to': last_day_in_month,
                        'state': 'confirm',
                        'holiday_type': 'employee'
                    })
                    leave.action_validate_leave()

            # Vérifier nombre d'allocations annuelles
            allocations_count = self.env['hr.leave'].search_count([
                ('employee_id', '=', employee.id),
                ('holiday_status_id', '=', leave_type.id),
                ('state', '=', 'validate'),
                ('holiday_type', '=', 'employee'),
            ])
            _logger.info(f'NB allocations légales cette année pour {employee.name}: {allocations_count}')

    
   