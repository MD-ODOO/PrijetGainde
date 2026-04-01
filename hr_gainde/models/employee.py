# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)
DATE_FORMAT = '%Y-%m-%d'

class HrEmployee(models.Model):
    _inherit = "hr.employee"


    national_agent = fields.Boolean(compute='_compute_nationality', store=True)
    
    marital = fields.Selection(
        selection=[
            ('single', 'Célibataire'),
            ('married', 'Marié(e)'),
            ('divorced', 'Divorcé(e)'),
            ('widower', 'Veuf / Veuve'),
        ],
        string="Situation matrimoniale"
    )
    
    categ_for_prime = fields.Many2many(
    'hr.categ.prime',
    'hr_employee_categ_prime_rel',  # table relation
    'employee_id',                  # colonne vers hr.employee
    'categ_prime_id',               # colonne vers hr.categ.prime
    string='Catégorie Prime',
    copy=True
    )
    # -----------------------
    # Enfants
    # -----------------------
    registration_number = fields.Char("Identifiant")
    ipres_number = fields.Char("N° IPRES")
    num_css = fields.Char(string='Numero CSS')
    datessaidebu = fields.Date(string='Début Essai')
    datessaifin = fields.Date(string='Fin Essai')
 
    carte_consule=fields.Char( string="Carte Consulaire")
    children_ids = fields.One2many('hr.employee.child', 'employee_id',string='Enfants en Charge')
    husband_ids = fields.One2many('hr.employee.husband', 'employee_id',string='Conjoint(e)')
    
    child_all_count = fields.Integer(compute='_compute_child_all_count',store=True)
   
    husband_all_count = fields.Integer(compute='_compute_husband_all_count',store=True)
    number_husbi_work = fields.Integer(compute='_compute_number_of_hus_work', store=True)
   
    number_no_twenty_one_children = fields.Integer(compute='_compute_number_of_minor_children', store=True)
    has_one_to_many_children_deceased = fields.Boolean(compute='_compute_has_deceased_child', store=True)
    has_adopted_child = fields.Boolean(compute='_compute_has_adopted_child', store=True)
    children = fields.Integer(compute='_compute_children_supported', store=True)
    holder_of_disability_pension = fields.Boolean(u'Conjoint(e) Avec Revenu')

    # -----------------------
    # Fiscalité / TRIMF
    # -----------------------
    husband_revenu = fields.Boolean("Conjointe avec revenu")
    trimf = fields.Float(compute='_compute_trimf', store=True, default=1)
    nb_part = fields.Float('IR',compute='_compute_nb_part', store=True)


    # -----------------------
    # Banque / Fonction / Spouse
    # -----------------------
    bank_ids = fields.One2many('hr.bank.employee', 'employee_id', string='Numéros de compte')

    # -----------------------
    # Diplôme / Entrée
    # -----------------------
   


    # ========================================================
    # COMPUTE FUNCTIONS
    # ========================================================
    @api.depends('children_ids')
    def _compute_child_all_count(self):
        for emp in self:
            emp.child_all_count = len(emp.children_ids)
    
    @api.depends('husband_ids')
    def _compute_husband_all_count(self):
        for emp in self:
            emp.husband_all_count = len(emp.husband_ids)

    @api.depends('husband_ids')
    def _compute_number_of_hus_work(self):
        for emp in self:
            emp.number_husbi_work = len(
            emp.husband_ids.filtered(lambda c: c.holder_of_disability_pension)
        )

    @api.depends('children_ids')
    def _compute_number_of_minor_children(self):
        for emp in self:
            emp.number_no_twenty_one_children = len(emp.children_ids.filtered(lambda c: not c.no_twenty_one))

    @api.depends('children_ids.supported')
    def _compute_children_supported(self):
        for emp in self:
            emp.children = len(emp.children_ids.filtered(lambda c: c.supported))

    @api.depends('children_ids.deceased')
    def _compute_has_deceased_child(self):
        for emp in self:
            emp.has_one_to_many_children_deceased = any(c.deceased for c in emp.children_ids)

    @api.depends('children_ids.adopted','children_ids.deceased')
    def _compute_has_adopted_child(self):
        for emp in self:
            emp.has_adopted_child = any(c.adopted and not c.deceased for c in emp.children_ids)


    @api.depends('country_id')
    def _compute_nationality(self):
        for emp in self:
            emp.national_agent = emp.country_id.code == 'SN' if emp.country_id else False

    @api.depends('husband_ids.holder_of_disability_pension')
    def _compute_trimf(self):
        for emp in self:
            # Base légale
            trimf = 1
    
            # Conjoints sans revenu
            spouses_without_income = emp.husband_ids.filtered(
                lambda h: not h.holder_of_disability_pension
            )
    
            trimf += len(spouses_without_income)
    
            emp.trimf = trimf

                

    @api.depends(
    'marital',
    'children_ids.supported',
    'children_ids.deceased',
    'children_ids.adopted',
    'husband_ids.holder_of_disability_pension'
    )
    def _compute_nb_part(self):
        for emp in self:
            part = 1.0  # base fiscale obligatoire
    
            # =========================
            # MAJORATION MARIAGE
            # =========================
            if emp.marital == 'married':
                part += 0.5
    
            # =========================
            # CONJOINTS SANS REVENU
            # =========================
            spouses_supported = emp.husband_ids.filtered(
                lambda h: not h.holder_of_disability_pension
            )
            part += len(spouses_supported) * 0.5
    
            # =========================
            # ENFANTS À CHARGE
            # =========================
            children_supported = emp.children_ids.filtered(
                lambda c: c.supported and not c.deceased
            )
            part += len(children_supported) * 0.5
    
            # =========================
            # MAJORATIONS EXCEPTIONNELLES
            # =========================
            if any(c.deceased for c in emp.children_ids):
                part += 0.5
    
            if any(c.adopted and not c.deceased for c in emp.children_ids):
                part += 0.5
    
            emp.nb_part = max(part, 1.0)
    
    @api.onchange('marital')
    def _onchange_marital_clear_husband(self):
        if self.marital == 'married':
            self.husband_ids = [(5, 0, 0)]

   
  
   


   


# -----------------------
# Cerco Category
# -----------------------
class CategPrime(models.Model):
    _name = 'hr.categ.prime'
    _description = "catégorie de l'employé"
    
    name = fields.Char(string='Catégorie ', required=True)
    
    employee_ids = fields.Many2many(
        'hr.employee',
        'hr_employee_categ_prime_rel',  # même table relation
        'categ_prime_id',               # colonne vers catégorie
        'employee_id',                  # colonne vers employee
        string="Employés"
    )

    _sql_constraints = [
    ('name_unique', 'unique(name)', 'Cette catégorie existe déjà !')
     ]
   
# -----------------------
# Cerco VPI
# -----------------------





    





