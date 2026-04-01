# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, date
import logging

_logger = logging.getLogger(__name__)

class HrLeave(models.Model):
    _inherit = "hr.leave"

    refusal_motivation = fields.Text(string='Motif du refus')
    code = fields.Char(string='Code')
    is_absence = fields.Boolean(string="Absence", readonly=True)
    supporting_document = fields.Many2many(
        'ir.attachment',
        'case_supporting_document_attachment_rel',
        'case_id',
        'attachment_id',
        string='Pièces justificatives',
        help="Vous pouvez ajouter ici des pièces justifiant l'absence"
    )
    date_posted = fields.Datetime(string="Date de la soumission", readonly=True)
    resume_date = fields.Date(string="Date de reprise", compute='_compute_resume_date', store=True)

    # =====================
    # Dépendances et onchange
    # =====================
    @api.onchange('is_absence')
    def _onchange_status_id(self):
        status_domain = []
        leave_type_model = self.env['hr.leave.type']
        if self.is_absence:
            status_domain = leave_type_model.search([('is_legal_leave', '=', False)]).ids
        else:
            status_domain = leave_type_model.search([('is_legal_leave', '=', True)]).ids
        return {'domain': {'holiday_status_id': [('id', 'in', status_domain)]}}

    # =====================
    # Calcul de la date de reprise
    # =====================
    @api.depends('date_to')
    def _compute_resume_date(self):
        for leave in self:
            if leave.date_to:
                next_day = leave.date_to
                # Sauter les week-ends
                while next_day.weekday() in (5, 6):  # 5 = samedi, 6 = dimanche
                    next_day += timedelta(days=1)
                leave.resume_date = next_day

    # =====================
    # Validation avec notification
    # =====================
    def action_validate_leave(self):
        for leave in self:
            # Vérification des droits
            if leave.leave_type_request_unit == 'remove':
                rh_users = leave.employee_id.company_id.rh_team
                if self.env.user not in rh_users:
                    raise ValidationError(_("Vous n'êtes pas autorisé à valider cette demande."))

            # Notification
            leave.message_post(
                body=_("Une demande de congé vient d'être validée."),
                message_type='notification'
            )
        return super().action_validate_leave()

    # =====================
    # Notification de reprise
    # =====================
    def trigger_resume_notification(self):
        today = date.today()
        for leave in self.filtered(lambda l: not l.is_absence and l.resume_date):
            if leave.resume_date <= today:
                self.env['mail.mail'].create({
                    'subject': "Reprise de service",
                    'author_id': self.env.user.partner_id.id,
                    'email_from': self.env.user.email or '',
                    'email_to': leave.employee_id.work_email or '',
                    'body_html': _(
                        "<p>Bonjour,</p>"
                        "<p>Nous vous informons que la reprise de service de <b>{employee}</b> est prévue le <b>{resume}</b>.</p>"
                        "<p>Type de congé : {leave_type}<br/>"
                        "Date de départ : {date_from}<br/>"
                        "Nombre de jours : {days}</p>"
                    ).format(
                        employee=leave.employee_id.name,
                        resume=leave.resume_date,
                        leave_type=leave.leave_type_id.name,
                        date_from=leave.date_from,
                        days=leave.number_of_days
                    )
                })
