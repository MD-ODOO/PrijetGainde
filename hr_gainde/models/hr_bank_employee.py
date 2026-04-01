# -*- coding: utf-8 -*-

from odoo import models, fields, api, _



class HrBankEmployee(models.Model):
    _name = 'hr.bank.employee'
    _description = 'Compte bancaire employé'
    _rec_name = 'bank_id'
    
    def action_confirm_unlink(self):
        return {
        'type': 'ir.actions.act_window',
        'name': _('Confirmation de suppression'),
        'res_model': 'hr.bank.employee',
        'view_mode': 'form',
        'target': 'new',
        'context': {
            'active_ids': self.ids,
            'confirm_delete': True,
        }
    }

    name = fields.Char(string='Nom affiché', store=True)
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employé',
        required=True,
        ondelete='cascade'
    )
    bank_id = fields.Many2one(
        'res.bank',
        string='Banque',
        required=True
    )
    number = fields.Char(
        string='Numéro de compte',
        required=True
    )
    is_first_bank = fields.Boolean(
        string='Compte principal ?'
    )
    amount = fields.Float(
        string='Montant virement'
    )
    code_rib = fields.Char(
        string='Clé RIB'
    )
    code_bank = fields.Char(
        string='Code Banque'
    )
    adress_bank = fields.Char(
        string='Adresse'
    )
    code_guichet = fields.Char(
        string='Code Agence'
    )
    lib_virement = fields.Many2one(
        'hr.virement.libelle',
        string='libellé Virement'
    )
    libelle = fields.Selection([('principal','Compte Principal'),('subvention','Subvention Immobilier'),('partiel','Virement Partiel')], string='Libellé')

    # =====================
    # NAME GET
    # =====================
   
                


class HrVirementLibell(models.Model):
    _name = 'hr.virement.libelle'
    _description = 'Libelle'
    
    

    name = fields.Char(string='Libellé Virement', store=True)

class HrBankEmp(models.Model):
    _inherit = 'res.bank'
    _description = 'Bank Employee'
    
    
    employeebank_id = fields.One2many('hr.bank.employee','bank_id',string='Employés')
   