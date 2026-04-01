# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################


from odoo import models, fields, _


class SurveyTemplate(models.Model):
    _name = 'survey.template'
    _description = 'Survey Template'

    name = fields.Char(string='Name', required=True)
    survey_ids = fields.Many2many('survey.survey', string='Survey')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: