# -*- coding: utf-8 -*-

from datetime import datetime

from dateutil.relativedelta import relativedelta

from odoo import models, fields, api
from odoo.exceptions import UserError


class CercoPayslipLinesCotisationIpres(models.TransientModel):
    _name = 'cerco.payslip.lines.cotisation.ipres'
   # _inherit = 'report.report_xlsx.abstract'
    _description = 'Cotisation IPRES - Wizard'


    company_id = fields.Many2one(
        'res.company',
        string='Entreprise',
        required=True,
        default=lambda self: self.env.company
    )
    date_from = fields.Date(string='Date de début', required=True, default=lambda self: datetime.today().replace(day=1))
    date_to = fields.Date(
        string='Date de fin',
        required=True,
        default=lambda self: (datetime.today().replace(day=1) + relativedelta(months=1, days=-1)).date()
    )
    wizard_id = fields.Char()
    
    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wiz in self:
            if wiz.date_from > wiz.date_to:
                raise ValueError("La date de début doit être antérieure à la date de fin.")
    
    def action_print_report(self):
        self.ensure_one()

        return self.env.ref(
        'paie_gainde.action_report_ipres'
    ).report_action(
        self,
        data={
            'date_from': self.date_from,
            'date_to': self.date_to,
        }
    )

    
    def action_print_vrs(self):
        self.ensure_one()

        if self.date_from > self.date_to:
            raise UserError("La date de debut doit etre inferieure a la date de fin.")

        payslips = self.env['hr.payslip'].search([
            ('company_id', '=', self.company_id.id),
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to),
            ('state', '=', 'done'),
        ])

        return self.env.ref(
            'paie_gainde.action_report_vrs'
        ).with_context(
            payslip_ids=payslips.ids,
            date_from=self.date_from,
            date_to=self.date_to,
            print_date=fields.Datetime.now().strftime('%Y-%m-%d %H:%M'),
        ).report_action(self)
    
    
    
    
    def action_print_livre_pdf(self):
        return self.env.ref(
            "paie_gainde.action_livre_paie_report"
        ).report_action(self)

   
    
    def action_export_xlsx(self):
        return {
            'type': 'ir.actions.report',
            'report_type': 'xlsx',
            'report_name': 'paie_gainde.report_ipres_xlsx',
            'data': {
                'date_from': self.date_from.isoformat(),
                'date_to': self.date_to.isoformat(),
            }
        }
        
        
    def action_print_ras(self):
        self.ensure_one()

        data = {
            'date_from': self.date_from,
            'date_to': self.date_to,
        }

        return self.env.ref(
            'paie_gainde.action_report_ras_dgid'
        ).report_action(
            None, data=data
        )
    
    def action_print_report_css(self):
        periode = self.date_from.strftime('%B %Y')

        return self.env.ref(
            'paie_gainde.action_report_css_declaration'
        ).report_action(self, data={
            'date_from': self.date_from,
            'date_to': self.date_to,
            'periode': periode,
            'date_declaration': self.date_from,
        })




