#-*- coding:utf-8 -*-
from odoo import models, api, fields
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class DeclarationRetenuReport(models.AbstractModel):
    _name = 'report.optesis_paie.report_declaration_retenu'

    @api.model
    def _get_payslip_lines(self, date_from, date_to):
        """
        Récupère toutes les lignes de bulletins pour la période
        """
        payslip_line_obj = self.env['hr.payslip.line']

        lines = payslip_line_obj.search([
            ('code', 'in', ['C1200','C2170','C2050','C2000']),
            ('slip_id.date_from', '>=', date_from),
            ('slip_id.date_to', '<=', date_to),
        ])

        totals = {
            'total_brut_male': 0.0, 'total_brut_female': 0.0,
            'total_ir_male': 0.0, 'total_ir_female': 0.0,
            'total_trimf_male': 0.0, 'total_trimf_female': 0.0,
            'total_cfce_male': 0.0, 'total_cfce_female': 0.0,
            'nb_male_brut': 0, 'nb_female_brut': 0,
            'nb_male_ir': 0, 'nb_female_ir': 0,
            'nb_male_trimf': 0, 'nb_female_trimf': 0,
            'nb_male_cfce': 0, 'nb_female_cfce': 0,
        }

        for line in lines:
            gender = line.employee_id.gender
            code = line.code

            if code == 'C1200':  # Brut
                if gender == 'male':
                    totals['total_brut_male'] += line.total
                    totals['nb_male_brut'] += 1
                else:
                    totals['total_brut_female'] += line.total
                    totals['nb_female_brut'] += 1
            elif code == 'C2170':  # IR
                if line.amount > 0:
                    if gender == 'male':
                        totals['total_ir_male'] += line.total
                        totals['nb_male_ir'] += 1
                    else:
                        totals['total_ir_female'] += line.total
                        totals['nb_female_ir'] += 1
            elif code == 'C2050':  # TRIMF
                if line.amount > 0:
                    if gender == 'male':
                        totals['total_trimf_male'] += line.total
                        totals['nb_male_trimf'] += 1
                    else:
                        totals['total_trimf_female'] += line.total
                        totals['nb_female_trimf'] += 1
            elif code == 'C2000':  # CFCE
                if line.amount > 0:
                    if gender == 'male':
                        totals['total_cfce_male'] += line.total
                        totals['nb_male_cfce'] += 1
                    else:
                        totals['total_cfce_female'] += line.total
                        totals['nb_female_cfce'] += 1

        return lines, totals

    @api.model
    def sum_total_brut(self, totals):
        return totals['total_brut_male'] + totals['total_brut_female']

    @api.model
    def sum_total_ir(self, totals):
        return totals['total_ir_male'] + totals['total_ir_female']

    @api.model
    def sum_total_trimf(self, totals):
        return totals['total_trimf_male'] + totals['total_trimf_female']

    @api.model
    def sum_total_cfce(self, totals):
        return totals['total_cfce_male'] + totals['total_cfce_female']

    @api.model
    def sum_total_total(self, totals):
        return self.sum_total_brut(totals) + self.sum_total_ir(totals) + self.sum_total_trimf(totals) + self.sum_total_cfce(totals)

    @api.model
    def format_periode(self, date_from, date_to):
        months = {
            1: "janvier", 2: "février", 3: "mars", 4: "avril", 5: "mai", 6: "juin",
            7: "juillet", 8: "août", 9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre"
        }
        start_date = datetime.strptime(date_from, '%Y-%m-%d')
        end_date = datetime.strptime(date_to, '%Y-%m-%d')
        if start_date.month == end_date.month and start_date.year == end_date.year:
            return f"{months[start_date.month]} {start_date.year}"
        else:
            return f"{months[start_date.month]} {start_date.year} au {months[end_date.month]} {end_date.year}"
