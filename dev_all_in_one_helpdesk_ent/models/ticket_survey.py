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
import werkzeug
from odoo.exceptions import ValidationError


class TicketSurvey(models.Model):
    _name = 'ticket.survey'
    _description = 'Ticket Survey'

    def send_survey_to_customer(self):
        if not self.ticket_id.partner_id:
            raise ValidationError(_('''Select Customer into Ticket'''))
        template_id = self.env.ref('dev_all_in_one_helpdesk_ent.template_start_survey_dev_helpdesk_survey')
        if template_id and self.ticket_id and self.ticket_id.partner_id.email:
            template_id.email_from = self.env.user and self.env.user.company_id and self.env.user.company_id.email or ''
            template_id.email_to = self.ticket_id.partner_id.email
            template_id.send_mail(self.id, force_send=True)

    def start_survey(self):
        if not self.ticket_id.partner_id:
            raise ValidationError(_('''Select Customer into Ticket'''))
        survey_url = werkzeug.urls.url_join(self.survey_id.get_base_url(), self.survey_id.get_start_url()) if self.survey_id else False
        return {
            'type': 'ir.actions.act_url',
            'name': "Start Survey",
            'target': 'new',
            'url': survey_url,
        }

    def get_survey_url(self):
        survey_url = werkzeug.urls.url_join(self.survey_id.get_base_url(), self.survey_id.get_start_url()) if self.survey_id else False
        return survey_url

    def print_survey(self):
        if self.survey_answer_id:

            res = self.survey_answer_id.sudo().action_print_answers()
            res.update({'target': 'new'})
            return res
        else:
            raise ValidationError(_('''No Answer found for '%s' Survey''') % (self.survey_id.title))

    def _compute_survey_answer_id(self):
        for rec in self:
            answer_id = False
            if rec.partner_id:

                last_answer_id  = self.env['survey.user_input'].search([('survey_id', '=', rec.survey_id.id),
                                                                        ('partner_id', '=', rec.partner_id.id)], order='id desc', limit=1)

                if last_answer_id:
                    answer_id = last_answer_id.id
            rec.survey_answer_id = answer_id

    ticket_id = fields.Many2one('helpdesk.ticket', string='Ticket', ondelete='cascade') # link
    survey_id = fields.Many2one('survey.survey', string='Survey', required=True)
    survey_answer_id = fields.Many2one('survey.user_input', string='Answer', compute='_compute_survey_answer_id')
    partner_id = fields.Many2one('res.partner', string='Customer', related='ticket_id.partner_id')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
