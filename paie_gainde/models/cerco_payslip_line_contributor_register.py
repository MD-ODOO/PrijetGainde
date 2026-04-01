# -*- coding: utf-8 -*-

from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import models, fields


class CercoPayslipLinesContributionRegister(models.TransientModel):
    _name = 'cerco.payslip.lines.contribution.register'
    _description = 'Déclaration des retenues à la source sur les salaires'

    date_from = fields.Date(
        string='Date de début',
        required=True,
        default=lambda self: datetime.today().replace(day=1)
    )

    date_to = fields.Date(
        string='Date de fin',
        required=True,
        default=lambda self: (datetime.today().replace(day=1) + relativedelta(months=1, days=-1)).date()
    )

    wizard_id = fields.Char()

    def print_report(self):
        """ Génère le rapport Retenue à la Source (IR) """
        self.ensure_one()

        data = {
            'ids': self.env.context.get('active_ids', []),
            'model': 'hr.contribution.register',
            'form': {
                'date_from': self.date_from,
                'date_to': self.date_to,
                'wizard_id': self.wizard_id,
            }
        }

        return self.env.ref('paie_gainde.action_report_declaration_retenu').report_action(self, data=data)
    

