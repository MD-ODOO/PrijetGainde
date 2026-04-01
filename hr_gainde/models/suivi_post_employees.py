# -*- coding: utf-8 -*-

from odoo import models, fields, api
import time
from datetime import datetime

DATE_FORMAT = '%Y-%m-%d'

class HrSuiviPost(models.Model):
    _name = 'hr.suivi.post'
    _description = 'Suivi des postes employés'
    _order = 'sequence'

    sequence = fields.Integer(string="Sequence", default=1)
    employee_id = fields.Many2one('hr.employee', string="Employé")
    poste_id = fields.Many2one('hr.job', string='Poste')
    post_duration = fields.Char(string="Ancienneté au poste", compute='_compute_duration_post')
    contrat_type = fields.Selection([('cdd', 'CDD'), ('cdi', 'CDI'), ('stage','Stage')], string='Type de contrat')
    categ_id = fields.Many2one('cerco.category', string='Catégorie')
    renouvellement = fields.Boolean(string='Renouvellement ?')
    grade = fields.Selection(
        [('cap', 'CAP'), ('bfem', 'BFEM'), ('bep', 'BEP'), ('bac', 'BAC'), 
         ('b2', 'BAC+2'), ('b3', 'BAC+3'), ('b4', 'BAC+4'), ('b5', 'BAC+5')], 
        string="Niveau d'étude"
    )
    diplome = fields.Char(string="Diplôme")
    date_start = fields.Date(string="Date de début", required=True)
    date_stop = fields.Date(string="Date de fin")

    @api.depends('date_start', 'date_stop')
    def _compute_duration_post(self):
        for record in self:
            if not record.date_start:
                record.post_duration = ''
                continue
            to_dt = datetime.strptime(record.date_start, DATE_FORMAT)
            today = datetime.strptime(time.strftime(DATE_FORMAT), DATE_FORMAT) if not record.date_stop else datetime.strptime(record.date_stop, DATE_FORMAT)
            delta = today - to_dt
            years = delta.days // 365
            months = int((delta.days % 365) / 30)
            record.post_duration = f"{years} An(s) et {months} Mois"
