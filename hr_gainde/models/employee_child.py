# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError
import logging

log = logging.getLogger(__name__)

# =========================================
# Enfant
# =========================================
class HrEmployeeChild(models.Model):
    _name = 'hr.employee.child'
    _inherit = ['documents.mixin']
    _description = "Enfant de l'employé"

 
    name = fields.Char(string="Prénom", required=True)
    date_of_birth = fields.Date(string='Date de naissance', required=True)
    employee_id = fields.Many2one('hr.employee', string="Employé", ondelete='cascade')
    gender = fields.Selection([('male','Masculin'),('female','Féminin')], string='Genre')
    deceased = fields.Boolean(string='Décédé(e)')
    infirm = fields.Boolean(string='Infirme')
    adopted = fields.Boolean(string='Adopté(e)')

    age_int = fields.Integer(string="Âge Employé", compute="_compute_age", store=True)
    age = fields.Char(
    string="Âge",
    compute="_compute_age_display",
    readonly=True) 
    
    no_twenty_one = fields.Boolean(string="A plus de 21 ans", compute="_compute_is_over_21", store=True)
    supported = fields.Boolean(string="Pris(e) en charge ?", compute='_compute_is_supported', store=True)

    document_ids = fields.Many2many(
        'documents.document',
        'child_document_rel',
        'child_id',
        'document_id',
        string="Documents justificatifs"
    )
    document_count = fields.Integer(string="Documents", compute="_compute_document_count", store=True)

    justificatif = fields.Boolean(
        string="Justificatif Validé",
        default=False,
    )
    justificatif_readonly = fields.Boolean(
        string="Justificatif verrouillé",
        compute='_compute_justificatif_readonly',
        store=True
    )

    # ----------------------------------------------------
    # COMPUTE
    # ----------------------------------------------------
   # @api.depends('date_of_birth')
   # def _compute_age(self):
    #    today = date.today()
     #   for rec in self:
      #      if rec.date_of_birth:
       #         delta = relativedelta(today, rec.date_of_birth)
        #        rec.age_int = delta.years
         #       rec.age = f"{delta.years}"
          #  else:
           #     rec.age_int = 0
            #    rec.age = "0 an"
    
    
    @api.depends('date_of_birth')
    def _compute_age(self):
        today = date.today()
        for rec in self:
            if rec.date_of_birth:
                rec.age_int = relativedelta(today, rec.date_of_birth).years
            else:
                rec.age_int = 0
                
    def _compute_age_display(self):
        for rec in self:
            rec.age = f"{rec.age_int}" if rec.age_int else "0"

    @api.depends('date_of_birth')
    def _compute_is_over_21(self):
        today = date.today()
        for rec in self:
            if rec.date_of_birth:
                rec.no_twenty_one = relativedelta(today, rec.date_of_birth).years > 21
            else:
                rec.no_twenty_one = False
    
    

    @api.depends('no_twenty_one','justificatif')
    def _compute_is_supported(self):
        for rec in self:
            rec.supported = not (rec.no_twenty_one and not rec.justificatif)

    @api.depends('document_ids')
    def _compute_document_count(self):
        for rec in self:
            rec.document_count = len(rec.document_ids)

    @api.depends('document_ids')
    def _compute_justificatif_readonly(self):
        for rec in self:
            rec.justificatif_readonly = not bool(rec.document_ids)

    # ----------------------------------------------------
    # ACTIONS
    # ----------------------------------------------------
    def action_open_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Justificatifs',
            'res_model': 'documents.document',
            'view_mode': 'kanban,list,form',
            'domain': [
                ('res_model', '=', self._name),
                ('res_id', '=', self.id),
                ('active', '=', True),  # documents actifs seulement
            ],
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
                'active_test': True,
            },
            'target': 'current',
        }

    # ----------------------------------------------------
    # CONTRAINTES / WRITE
    # ----------------------------------------------------
   
    # ----------------------------------------------------
    # DISPLAY NAME
    # ----------------------------------------------------
    def name_get(self):
        return [(rec.id, f"{rec.firstname} {rec.name}".strip()) for rec in self]


# =========================================
# Conjointe / Femme
# =========================================
class HrEmployeeHusband(models.Model):
    _name = 'hr.employee.husband'
    _inherit = ['documents.mixin']
    _description = "Femme de l'employé"


    name = fields.Char(string="Prénom et NOM", required=True)
    holder_of_disability_pension = fields.Boolean(string="Conjointe Avec Revenu ?", default=True)
    employee_id = fields.Many2one('hr.employee', string="Employé", ondelete='cascade')
    date_of_birth = fields.Date(string='Date de naissance', required=True)
    gender = fields.Selection([('male','Masculin'),('female','Féminin')], string='Genre')

    document_ids = fields.One2many(
        'documents.document',
        'res_id',
        domain=lambda self: [('res_model','=',self._name)],
        string="Documents"
    )
    document_count = fields.Integer(string="Nbr Doc", compute="_compute_document_count", store=True)
    
    date_mariage = fields.Date(string='Date de Mariage')

    # ----------------------------------------------------
    # COMPUTE
    # ----------------------------------------------------
    def _compute_document_count(self):
        for rec in self:
            rec.document_count = len(rec.document_ids)

    # ----------------------------------------------------
    # ACTIONS
    # ----------------------------------------------------
    
        
    def action_open_income_justification(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Justificatifs',
            'res_model': 'documents.document',
            'view_mode': 'kanban,list,form',
            'domain': [
                ('res_model', '=', self._name),
                ('res_id', '=', self.id),
                ('active', '=', True),  # documents actifs seulement
            ],
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
                'active_test': True,
            },
            'target': 'current',
        }
    
    def action_open_marriage_certificate(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Mariage',
            'res_model': 'documents.document',
            'view_mode': 'kanban,list,form',
            'domain': [
                ('res_model', '=', self._name),
                ('res_id', '=', self.id),
                ('active', '=', True),  # documents actifs seulement
            ],
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
                'active_test': True,
            },
            'target': 'current',
        }
   

    # ----------------------------------------------------
    # CONTRAINTES
    # ----------------------------------------------------
   

    # ----------------------------------------------------
    # DISPLAY NAME
    # ----------------------------------------------------
    def name_get(self):
        return [(rec.id, f"{rec.firstname} {rec.name}".strip()) for rec in self]
