# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date
import logging

_logger = logging.getLogger(__name__)




class CercoRequestMedical(models.Model):
    _name = 'cerco.request.medical'
    _description = 'Demande médicale'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'employee_id'
    _order = 'date desc'

    # =====================
    # FIELDS
    # =====================
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employé',
        required=True,
        default=lambda self: self.env['hr.employee'].search(
            [('user_id', '=', self.env.user.id)], limit=1
        )
    )

    date = fields.Date(
        string='Date de la demande',
        default=fields.Date.context_today,
        tracking=True
    )

    close_date = fields.Date(string='Date de clôture', tracking=True)

    comment = fields.Text(string='Commentaire')

    type_id = fields.Many2one(
        'cerco.request.type',
        string='Type de demande',
        required=True
    )

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('submit', 'Envoyée'),
        ('validate', 'Validée'),
        ('close', 'Clôturée'),
        ('cancel', 'Refusée')
    ], default='draft', tracking=True, copy=False)

    # approver_ids = fields.One2many(
    #     'request.medical.approver',
    #     'request_id',
    #     string='Approbateurs'
    # )

    attachment_number = fields.Integer(
        compute='_compute_attachment_number',
        string='Nombre de pièces jointes'
    )

    # =====================
    # COMPUTES
    # =====================
    def _compute_attachment_number(self):
        attachment_data = self.env['ir.attachment'].read_group(
            [('res_model', '=', self._name), ('res_id', 'in', self.ids)],
            ['res_id'],
            ['res_id']
        )
        count_map = {a['res_id']: a['res_id_count'] for a in attachment_data}
        for rec in self:
            rec.attachment_number = count_map.get(rec.id, 0)

    # =====================
    # ACTIONS
    # =====================
    def action_submit(self):
        self.ensure_one()

        if self.env.user != self.employee_id.user_id:
            raise ValidationError(
                _("Seul le propriétaire de la demande peut l’envoyer.")
            )

        self._subscribe_rh_team()

        self.write({'state': 'submit'})

        self.env['request.medical.approver'].create({
            'request_id': self.id,
            'user_id': self.env.user.id,
            'date_approved': fields.Datetime.now(),
            'state': 'submit'
        })

    def action_close(self):
        self.write({
            'state': 'close',
            'close_date': date.today()
        })

    def action_open_attachments(self):
        self.ensure_one()
        return {
            'name': _('Pièces jointes'),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.attachment',
            'view_mode': 'kanban,tree,form',
            'domain': [
                ('res_model', '=', self._name),
                ('res_id', '=', self.id)
            ],
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id
            }
        }

    def open_wizard_approval(self):
        self.ensure_one()
        return {
            'name': _("Approbation"),
            'type': 'ir.actions.act_window',
            'res_model': 'request.medical.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id}
        }

    def open_wizard_refusal(self):
        self.ensure_one()
        return {
            'name': _("Refus"),
            'type': 'ir.actions.act_window',
            'res_model': 'request.medical.refusal',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id}
        }

    # =====================
    # UTIL
    # =====================
    def _subscribe_rh_team(self):
        rh_users = self.employee_id.company_id.rh_team
        partners = rh_users.mapped('partner_id')
        self.message_subscribe(partner_ids=partners.ids)
