 # -*- coding: utf-8 -*-

from odoo import models, fields, api

class HrContributionRegister(models.Model):
    _inherit = 'hr_payroll.contribution.register'

    def open_wizard_function(self):
        """Ouvre le wizard général de contributions"""
        wizard = self.env['cerco.payslip.lines.contribution.register'].create({})
        return {
            'name': 'Période',
            'type': 'ir.actions.act_window',
            'res_model': 'cerco.payslip.lines.contribution.register',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    def open_wizard_function_css(self):
        """Ouvre le wizard sécurité sociale"""
        wizard = self.env['cerco.payslip.lines.securite.sociale'].create({})
        return {
            'name': 'Période',
            'type': 'ir.actions.act_window',
            'res_model': 'cerco.payslip.lines.securite.sociale',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    def open_wizard_function_ipres(self):
        """Ouvre le wizard cotisation IPRES"""
        wizard = self.env['cerco.payslip.lines.cotisation.ipres'].create({})
        return {
            'name': 'Période',
            'type': 'ir.actions.act_window',
            'res_model': 'cerco.payslip.lines.cotisation.ipres',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }
