# -*- coding: utf-8 -*-
from odoo import api, models
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class PayslipReport(models.AbstractModel):
    _name = 'report.paie_gainde.report_payroll_cesag'
    _description = 'Bulletin de Paie Cesag'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['hr.payslip'].browse(docids)
        return {
            'docs': docs,
            'get_payslip_imposable': self.get_payslip_imposable,
            'get_payslip_cotisation': self.get_payslip_cotisation,
            'get_payslip_non_imposable': self.get_payslip_non_imposable,
            'get_payslip_retenu': self.get_payslip_retenu,
            'get_total_gains': self.get_total_gains,
            'get_total_charg_sal': self.get_total_charg_sal,
            'get_total_charge_pat': self.get_total_charge_pat,
            'get_sal_brut_imp': self.get_sal_brut_imp,
            'get_sal_brut': self.get_sal_brut,
            'get_sal_net': self.get_sal_net,
            'get_val_annuel': self.get_val_annuel,
            'get_nombre': self.get_nombre,
            'get_payment_mode': self.get_payment_mode,
            'get_marital': self.get_marital,
            'get_contract_type': self.get_contract_type,
        }

    def get_payslip_imposable(self, payslip):
        lines = payslip.line_ids.filtered(lambda l: l.category_id.code in ['INDM','BASE','BRUT'] and l.appears_on_payslip)
        payslip.total_brut = sum(lines.mapped('total'))
        payslip.total_gain = sum(lines.mapped('total'))
        return lines

    def get_payslip_cotisation(self, payslip):
        lines = payslip.line_ids.filtered(
            lambda l: l.appears_on_payslip and (
                l.category_id.code in ['COMP','SALC','IR','TRIMF'] or l.code == 'C2170'
            )
        )
        payslip.total_charg_pat = sum(l.total for l in lines if l.category_id.code == 'COMP')
        payslip.total_charg_sal = sum(l.total for l in lines if l.category_id.code != 'COMP')
        return lines

    def get_payslip_non_imposable(self, payslip):
        lines = payslip.line_ids.filtered(lambda l: l.category_id.code == 'NOIMP' and l.appears_on_payslip)
        payslip.total_brut += sum(lines.mapped('total'))
        payslip.total_gain += sum(lines.mapped('total'))
        return lines

    def get_payslip_retenu(self, payslip):
        lines = payslip.line_ids.filtered(lambda l: l.category_id.code == 'DED' and l.code != 'C2170' and l.appears_on_payslip)
        payslip.total_charg_sal += sum(lines.mapped('total'))
        return lines

    def get_total_gains(self, payslip):
        return getattr(payslip, 'total_gain', 0)

    def get_total_charg_sal(self, payslip):
        return getattr(payslip, 'total_charg_sal', 0)

    def get_total_charge_pat(self, payslip):
        return getattr(payslip, 'total_charg_pat', 0)

    def get_sal_brut_imp(self, payslip):
        lines = payslip.line_ids.filtered(lambda l: l.category_id.code in ['BRUT','AVN'])
        return sum(lines.mapped('total'))

    def get_sal_brut(self, payslip):
        return getattr(payslip, 'total_brut', 0)

    def get_sal_net(self, payslip):
        lines = payslip.line_ids.filtered(lambda l: l.category_id.code == 'NET')
        return sum(lines.mapped('total'))

    def get_val_annuel(self, date_from, employee_id):
        year = datetime.strptime(date_from, '%Y-%m-%d').year
        payslips = self.env['hr.payslip'].search([('employee_id', '=', employee_id)])
        payslips_year = payslips.filtered(lambda p: datetime.strptime(p.date_from, '%Y-%m-%d').year == year)

        sal_brut_an = sum(p.line_ids.filtered(lambda l: l.category_id.code == 'BTOTAL').mapped('total') for p in payslips_year)
        charg_pat_an = sum(p.line_ids.filtered(lambda l: l.category_id.code == 'TCOMP').mapped('total') for p in payslips_year)
        charg_sal_an = sum(p.line_ids.filtered(lambda l: l.category_id.code == 'TSALC').mapped('total') for p in payslips_year)
        heure_travail_an = sum((173.33/30) * p.worked_days_line_ids[0].number_of_days if p.worked_days_line_ids else 0 for p in payslips_year)

        return [{
            'sal_brut_an': sal_brut_an,
            'charg_pat_an': charg_pat_an,
            'charg_sal_an': charg_sal_an,
            'heure_travail_an': heure_travail_an
        }]

    def get_nombre(self, nb_work):
        return (173.33 / 30) * nb_work

    def get_payment_mode(self, payslip):
        return dict(payslip._fields['typePaiement'].selection).get(payslip.typePaiement, '')

    def get_marital(self, employee):
        return dict(employee._fields['marital'].selection).get(employee.marital, '')

    def get_contract_type(self, employee):
        return dict(employee._fields['contrat_type'].selection).get(employee.contrat_type, '')

