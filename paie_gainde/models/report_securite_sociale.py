# -*- coding: utf-8 -*-
from odoo import models, api
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class ReportSecuriteSociale(models.AbstractModel):
    _name = 'report.paie_gainde.report_css'
    _description = 'Rapport Sécurité Sociale'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['cerco.payslip.lines.securite.sociale'].browse(docids)

        # Initialisation
        self._init_totals()

        for doc in docs:
            self._compute_lines(doc)

        return {
            'doc_ids': docids,
            'doc_model': 'cerco.payslip.lines.securite.sociale',
            'docs': docs,
            'get_date_from': self.get_date_from,
            'get_date_to': self.get_date_to,

            # Totaux
            'total_brut_male': self.total_brut_male,
            'total_base_male': self.total_base_male,
            'total_prestfam_male': self.total_prestfam_male,
            'total_acw_male': self.total_acw_male,

            'total_brut_female': self.total_brut_female,
            'total_base_female': self.total_base_female,
            'total_prestfam_female': self.total_prestfam_female,
            'total_acw_female': self.total_acw_female,

            'sum_total_brut': self.sum_total_brut,
            'sum_total_base': self.sum_total_base,
            'sum_total_prestfam': self.sum_total_prestfam,
            'sum_total_acw': self.sum_total_acw,
            'sum_total_cotisation': self.sum_total_cotisation,

            # Compteurs
            'get_male_brut_count': lambda: self.nb_male_brut,
            'get_female_brut_count': lambda: self.nb_female_brut,
            'get_total_brut_count': lambda: self.nb_male_brut + self.nb_female_brut,

            'get_male_prestfam_count': lambda: self.nb_male_prestfam,
            'get_female_prestfam_count': lambda: self.nb_female_prestfam,
            'get_total_prestfam_count': lambda: self.nb_male_prestfam + self.nb_female_prestfam,

            'get_male_awc_count': lambda: self.nb_male_awc,
            'get_female_awc_count': lambda: self.nb_female_awc,
            'get_total_awc_count': lambda: self.nb_male_awc + self.nb_female_awc,
        }

    # --------------------------------------------------
    # INITIALISATION
    # --------------------------------------------------
    def _init_totals(self):
        self.total_brut_male = 0.0
        self.total_base_male = 0.0
        self.total_prestfam_male = 0.0
        self.total_acw_male = 0.0

        self.total_brut_female = 0.0
        self.total_base_female = 0.0
        self.total_prestfam_female = 0.0
        self.total_acw_female = 0.0

        self.nb_male_brut = 0
        self.nb_female_brut = 0
        self.nb_male_prestfam = 0
        self.nb_female_prestfam = 0
        self.nb_male_awc = 0
        self.nb_female_awc = 0

    # --------------------------------------------------
    # CALCULS
    # --------------------------------------------------
    def _compute_lines(self, wizard):
        slips = self.env['hr.payslip'].search([
            ('date_from', '>=', wizard.date_from),
            ('date_to', '<=', wizard.date_to),
            ('state', '=', 'done'),
        ])

        for slip in slips:
            emp = slip.employee_id
            gender = emp.gender

            for line in slip.line_ids:
                if line.code == 'C1200':
                    self._add_brut(gender, line.total)
                elif line.code == 'C2010':
                    self._add_prestfam(gender, line.amount, line.total)
                elif line.code == 'C2020':
                    self._add_acw(gender, line.total)

    def _add_brut(self, gender, amount):
        if gender == 'male':
            self.total_brut_male += amount
            self.nb_male_brut += 1
        else:
            self.total_brut_female += amount
            self.nb_female_brut += 1

    def _add_prestfam(self, gender, base, total):
        if gender == 'male':
            self.total_base_male += base
            self.total_prestfam_male += total
            self.nb_male_prestfam += 1
        else:
            self.total_base_female += base
            self.total_prestfam_female += total
            self.nb_female_prestfam += 1

    def _add_acw(self, gender, total):
        if gender == 'male':
            self.total_acw_male += total
            self.nb_male_awc += 1
        else:
            self.total_acw_female += total
            self.nb_female_awc += 1

    # --------------------------------------------------
    # TOTAUX
    # --------------------------------------------------
    def sum_total_brut(self):
        return self.total_brut_male + self.total_brut_female

    def sum_total_base(self):
        return self.total_base_male + self.total_base_female

    def sum_total_prestfam(self):
        return self.total_prestfam_male + self.total_prestfam_female

    def sum_total_acw(self):
        return self.total_acw_male + self.total_acw_female

    def sum_total_cotisation(self):
        return self.sum_total_prestfam() + self.sum_total_acw()

    # --------------------------------------------------
    # DATES
    # --------------------------------------------------
    def get_date_from(self):
        return datetime.strftime(self.date_from, '%d/%m/%Y')

    def get_date_to(self):
        return datetime.strftime(self.date_to, '%d/%m/%Y')
