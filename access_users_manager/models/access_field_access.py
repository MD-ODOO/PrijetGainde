# -*- coding: utf-8 -*-
import warnings

from odoo import fields, models, api, _, service,tools
from odoo.exceptions import UserError
from odoo.http import request

from odoo.exceptions import ValidationError


class KsFieldAccess(models.Model):
    _name = 'field.access'
    _inherit = ['mail.thread']
    _description = 'Field Access'

    access_model_id = fields.Many2one('ir.model', string='Model', domain="[('id', 'in', access_profile_domain_model )]")
    access_field_id = fields.Many2many('ir.model.fields',
                                   string='Field')
    access_field_invisible = fields.Boolean(string='Invisible')
    access_field_readonly = fields.Boolean(string='Readonly')
    access_field_required = fields.Boolean(string='Required')
    access_field_external_link = fields.Boolean(string='Remove External Link')
    access_user_management_id = fields.Many2one('user.management', string='Management')
    access_profile_domain_model = fields.Many2many('ir.model', related='access_user_management_id.access_profile_domain_model')
    access_company_ids = fields.Many2many('res.company', related='access_user_management_id.access_company_ids')

    access_tracking = fields.Boolean(string="Tracking")

    @api.constrains('access_field_required', 'access_field_readonly', 'access_tracking')
    def access_check_field_access(self):
        # profile = self.env['user.management']
        for rec in self:
            if rec.access_field_required and rec.access_field_readonly:
                raise UserError(_('You can not set field as Readonly and Required at same time.'))
            elif rec.access_field_required and rec.access_field_invisible:
                raise UserError(_('You can not set field as Invisible and Required at same time.'))
            for field in rec.access_field_id:
                if rec.access_field_required:
                    if self.search([('access_field_invisible','=',True),('access_field_id','in',field.id),('access_user_management_id.access_user_ids','in',self.access_user_management_id.access_user_ids.ids)]):
                        raise UserError(_('You can not set field as Invisible and Required at same time.'))
                    elif self.search([('access_field_readonly','=',True),('access_field_id','in',field.id),('access_user_management_id.access_user_ids','in',self.access_user_management_id.access_user_ids.ids)]):
                        raise UserError(_('You can not set field as Readonly and Required at same time.'))
                elif rec.access_field_invisible:
                    if self.search([('access_field_required','=',True),('access_field_id','in',field.id),('access_user_management_id.access_user_ids','in',self.access_user_management_id.access_user_ids.ids)]):
                        raise UserError(_('You can not set field as Invisible and Required at same time.'))
                elif rec.access_field_readonly:
                    if self.search([('access_field_required','=',True),('access_field_id','in',field.id),('access_user_management_id.access_user_ids','in',self.access_user_management_id.access_user_ids.ids)]):
                        raise UserError(_('You can not set field as Readonly and Required at same time.'))
                if rec.access_tracking and (field.ttype == 'html' or field.ttype == 'one2many'):
                    raise ValidationError(_('You can not set Tracking for HTML and One2many fields.'))


    @api.constrains('access_field_id','access_tracking', 'access_company_ids', 'access_user_management_id.access_company_ids')
    def action_restart(self):
        self.env.registry.clear_cache()

    def get_track_fields(self):
        model_fields = []
        if self.access_tracking == True:
            for field_id in self.access_field_id:
                model_fields.append(field_id.name)
        return model_fields


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    @tools.ormcache('self.env.uid', 'self.env.su')
    def _track_get_fields(self):
        model_fields = {
            name
            for name, field in self._fields.items()
            if getattr(field, 'tracking', None) or getattr(field, 'track_visibility', None)
        }
        for value in self:
            extra_fields = value.get_track_fields()
            for i in extra_fields:
                model_fields.add(i)
        return model_fields and set(self.fields_get(model_fields, attributes=()))

    def get_track_fields(self):
        model_fields = []
        try:
            c_ids = request.httprequest.cookies.get('cids')
        except RuntimeError:  
            c_ids = None
        if c_ids:
            company_lst = [int(x) for x in c_ids.split('-')]
            fields_tracking = self.env['field.access'].sudo().search(
                [('access_model_id.model', '=', self._name),
                 ('access_user_management_id.active', '=', True),
                 ('access_user_management_id.access_user_ids', 'in', self._uid),
                 ('access_user_management_id.access_company_ids', 'in', company_lst),
                 ('access_tracking', '=', True)
                 ])
        else:
            fields_tracking = self.env['field.access'].sudo().search(
                [('access_model_id.model', '=', self._name),
                 ('access_user_management_id.active', '=', True),
                 ('access_user_management_id.access_user_ids', 'in', self._uid),
                 ('access_tracking', '=', True)
                 ])

        global_fields_tracking = self.env['global.tracking'].sudo().search(
            [('g_model_id.model', '=', self._name),
             ])
        for h in fields_tracking:
            field_ids = h.access_field_id.filtered(lambda field:field.ttype != 'html')
            for field_id in field_ids:
                model_fields.append(field_id.name)

        for field_id in global_fields_tracking.g_field_id:
                model_fields.append(field_id.name)
        return model_fields

