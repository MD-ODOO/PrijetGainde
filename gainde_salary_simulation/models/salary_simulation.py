# -*- coding: utf-8 -*-
from odoo import api, fields, models, _ 
from odoo.exceptions import ValidationError

from .salary_engine import TRANSPORT_AMOUNT, compute_family_parts, solve_gross_for_net

class GaindeSalarySimulation(models.Model):
    _name = 'gainde.salary.simulation'
    _description = 'Simulation de salaire net'
    _order = 'create_date desc, id desc'

    name = fields.Char(string='Référence', required=True, readonly=True, copy=False,
                       default=lambda self: _('Nouveau'))
    employee_id = fields.Many2one('hr.employee', string='Employé / Candidat', ondelete='set null')
    category_id = fields.Many2one('gainde.salary.category', string='Catégorie socio-professionnelle', required=True)
    status = fields.Selection(
        [('non_cadre', 'Non cadre'), ('cadre', 'Cadre')],
        string='Statut', required=True, default='non_cadre'
    )
    marital = fields.Selection([
        ('single', 'Célibataire'), ('married', 'Marié(e)'),
        ('divorced', 'Divorcé(e)'), ('widower', 'Veuf / Veuve')
    ], string='Situation matrimoniale', default='single', required=True)
    children_count = fields.Integer(string='Enfants à charge', default=0)
    spouse_has_income = fields.Boolean(
        string='Conjoint(e) avec revenu imposable',
        help='Information neutre : elle ne dépend pas du sexe du salarié ou du conjoint.'
    )
    part_ir = fields.Float(string='Parts IR', compute='_compute_family_parts', store=True, digits=(16, 2))
    trimf_parts = fields.Float(string='Personnes TRIMF', compute='_compute_family_parts', store=True, digits=(16, 2))
    net_target = fields.Monetary(
        string='Salaire net souhaité (Net à payer)', currency_field='currency_id',
        required=True, default=0.0
    )
    base_salary = fields.Monetary(string='Salaire de base', currency_field='currency_id', compute='_compute_simulation', store=True)
    gross = fields.Monetary(string='Brut simulé', currency_field='currency_id', compute='_compute_simulation', store=True)
    sursalaire = fields.Monetary(string='Sursalaire', currency_field='currency_id', compute='_compute_simulation', store=True)
    ir_amount = fields.Monetary(string='IR', currency_field='currency_id', compute='_compute_simulation', store=True)
    trimf_amount = fields.Monetary(string='TRIMF', currency_field='currency_id', compute='_compute_simulation', store=True)
    ipres_rg = fields.Monetary(string='IPRES RG', currency_field='currency_id', compute='_compute_simulation', store=True)
    ipres_rc = fields.Monetary(string='IPRES RC', currency_field='currency_id', compute='_compute_simulation', store=True)
    net_before_transport = fields.Monetary(string='Salaire net', currency_field='currency_id', compute='_compute_simulation', store=True)
    transport = fields.Monetary(string='Transport', currency_field='currency_id', compute='_compute_simulation', store=True)
    net_to_pay = fields.Monetary(string='Net à payer simulé', currency_field='currency_id', compute='_compute_simulation', store=True)
    currency_id = fields.Many2one(
        'res.currency', string='Devise',
        default=lambda self: self.env.company.currency_id, required=True, readonly=True
    )
    note = fields.Text(string='Résultat / observation', compute='_compute_note', store=True)

    @api.model
    def create(self, vals):
        if not vals.get('name') or vals.get('name') == _('Nouveau'):
            vals['name'] = self.env['ir.sequence'].next_by_code('gainde.salary.simulation') or _('Nouveau')
        return super().create(vals)

    @api.depends('marital', 'children_count', 'spouse_has_income')
    def _compute_family_parts(self):
        for record in self:
            record.part_ir, record.trimf_parts = compute_family_parts(
                record.marital, record.children_count, record.spouse_has_income
            )

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        for record in self:
            employee = record.employee_id
            if not employee:
                continue
            record.marital = employee.marital or 'single'
            record.children_count = len(
                employee.children_ids.filtered(lambda child: child.supported and not child.deceased)
            )
            record.spouse_has_income = bool(getattr(employee, 'husband_revenu', False))

    @api.constrains('children_count', 'net_target')
    def _check_inputs(self):
        for record in self:
            if record.children_count < 0:
                raise ValidationError(_('Le nombre d’enfants ne peut pas être négatif.'))
            if record.net_target < 0:
                raise ValidationError(_('Le salaire net souhaité ne peut pas être négatif.'))

    @api.depends('category_id', 'category_id.base_salary', 'status', 'net_target', 'part_ir', 'trimf_parts)
    def _compute_simulation(self):
        for record in self:
            base_salary = record.category_id.base_salary if record.category_id else 0.0
            result = solve_gross_for_net(
                record.net_target, base_salary, record.part_ir, record.trimf_parts, record.status
            )
            record.base_salary = base_salary
            record.gross = result['gross']
            record.sursalaire = max(result['gross'] - base_salary, 0.0)
            record.ir_amount = result['ir']
            record.trimf_amount = result['trimf']
            record.ipres_rg = result['ipres_rg']
            record.ipres_rc = result['ipres_rc']
            record.net_before_transport = result['net_before_transport']
            record.transport = TRANSPORT_AMOUNT
            record.net_to_pay = result['net_to_pay']

    @api.depends('net_target', 'net_to_pay', 'base_salary', 'gross', 'sursalaire')
    def _compute_note(self):
        for record in self:
            if not record.category_id:
                record.note = _('Sélectionnez une catégorie socio-professionnelle.')
                continue
            difference = record.net_to_pay - record.net_target
            if abs(difference) < 1.0:
                record.note = _('Simulation atteignant le salaire net souhaité.')
            elif difference > 0:
                record.note = _(
                    'Le salaire de base de la catégorie est supérieur au minimum nécessaire. '
                    'Le net simulé dépasse la cible de %.2f FCFA.'
                ) % difference
            else:
                record.note = _(
                    'Le net simulé est inférieur à la cible de %.2f FCFA. '
                    'Ajustez le salaire de base de la catégorie si nécessaire.'
                ) % abs(difference)

    def action_recompute(self):
        self._compute_family_parts()
        self._compute_simulation()
        self._compute_note()
        return True
