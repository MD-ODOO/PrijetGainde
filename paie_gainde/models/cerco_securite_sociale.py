# -*- coding: utf-8 -*-

from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import models, fields


class CercoPayslipLinesSecuriteSociale(models.TransientModel):
    _name = 'cerco.payslip.lines.securite.sociale'
    _description = 'Sécurité Sociale - Wizard'

    date_from = fields.Date(
        string='Date de début',
        required=True,
        default=lambda self: datetime.today().replace(day=1)
    )

    date_to = fields.Date(
        string='Date de fin',
        required=True,
        default=lambda self: (
            datetime.today().replace(day=1) + relativedelta(months=1, days=-1)
        ).date()
    )

    wizard_id = fields.Char()

    def print_report_css(self):
        """ Génère le rapport CSS (Sécurité Sociale) """
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

        return self.env.ref('paie_gainde.report_css').report_action(self, data=data)

