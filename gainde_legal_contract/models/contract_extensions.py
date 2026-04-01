from odoo import models, fields


class LegalContractEmployee(models.Model):
    """Pour CDD, CDI, Stagiaires (Personnes Physiques)"""
    _name = 'legal.contract.employee'
    _inherits = {'legal.contract': 'contract_id'}

    contract_id = fields.Many2one('legal.contract', required=True,
                                  ondelete='cascade')
    job_id = fields.Many2one('hr.job', string="Poste")
    salary_gross = fields.Float("Salaire Mensuel Brut")
    salary_in_words = fields.Char("Salaire en toutes lettres")


class LegalContractBusiness(models.Model):
    """Pour Marchés, Prestations, Protocoles (Personnes Morales)"""
    _name = 'legal.contract.business'
    _inherits = {'legal.contract': 'contract_id'}

    contract_id = fields.Many2one('legal.contract', required=True,
                                  ondelete='cascade')
    representative_name = fields.Char("Représentant Légal")
    guarantee_amount = fields.Float("Caution / Garantie")
    market_value = fields.Float("Valeur Totale du Marché")


class LegalContractNDA(models.Model):
    """Pour Accords de Confidentialité"""
    _name = 'legal.contract.nda'
    _inherits = {'legal.contract': 'contract_id'}

    contract_id = fields.Many2one('legal.contract', required=True,
                                  ondelete='cascade')
    secrecy_years = fields.Integer("Durée du secret (ans)", default=5)
