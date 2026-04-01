# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime
from dateutil import relativedelta
import logging

_logger = logging.getLogger(__name__)


class OrdreVirementHR(models.TransientModel):
    _name = 'wizard.ordre.virement.hr'
    _description = "Wizard pour l'ordre de virement RH"

    payslip_ids = fields.Many2many(
        'hr.payslip', 'payslip_wizard_rel',
        'wizard_id', 'payslip_id',
        string="Bulletins de Paye",
        required=True
    )

    date_start = fields.Date(
        string="Date début",
        default=lambda self: datetime.today().replace(day=1),
        required=True
    )

    date_stop = fields.Date(
        string="Date fin",
        default=lambda self: (
            datetime.today()
            + relativedelta.relativedelta(months=1, day=1, days=-1)
        ),
        required=True
    )

    bank_id = fields.Many2one(
        'res.bank',
        string='Banque',
        required=True
    )

    line_ids = fields.One2many(
        'wizard.ordre.virement.hr.line',
        'wizard_id',
        string="Détails des virements"
    )

    total_amount = fields.Float(
        string="Total à virer",
        compute="_compute_total_amount",
        store=False
    )

    # -----------------------------
    # DEFAULT GET
    # -----------------------------
    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        active_ids = self.env.context.get('active_ids')
        active_model = self.env.context.get('active_model')

        if active_model == 'hr.payslip' and active_ids:
            res['payslip_ids'] = [(6, 0, active_ids)]
        return res

    # -----------------------------
    # ONCHANGE BANQUE / BULLETINS
    # -----------------------------

    @api.onchange('bank_id', 'date_start', 'date_stop')
    def _onchange_bank_id(self):
        self.line_ids = [(5, 0, 0)]
    
        if not self.bank_id:
            self.payslip_ids = [(5, 0, 0)]
            return
    
        # 1️⃣ Chercher les employés ayant AU MOINS
        # un compte bancaire sur la banque sélectionnée
        employees = self.env['hr.bank.employee'].search([
            ('bank_id', '=', self.bank_id.id)
        ]).mapped('employee_id')
    
        if not employees:
            self.payslip_ids = [(5, 0, 0)]
            return
    
        # 2️⃣ Charger UNIQUEMENT les bulletins correspondants
        payslips = self.env['hr.payslip'].search([
            ('employee_id', 'in', employees.ids),
            ('date_from', '>=', self.date_start),
            ('date_to', '<=', self.date_stop),
            ('state', '=', 'paid'),  # recommandé
        ])
    
        self.payslip_ids = [(6, 0, payslips.ids)]
    
        # 3️⃣ Générer les lignes de virement
        lines = []
    
        for payslip in payslips:
            employee = payslip.employee_id
            net = payslip.amount_net or 0.0
    
            accounts = self.env['hr.bank.employee'].search([
                ('employee_id', '=', employee.id),
                ('bank_id', '=', self.bank_id.id)
            ])
    
            other_amount = sum(
                acc.amount for acc in accounts
                if acc.libelle != 'principal'
            )
    
            for acc in accounts:
                amount = acc.amount
                if acc.libelle == 'principal':
                    amount = net - other_amount
    
                if amount < 0:
                    raise ValidationError(_(
                        "Montant négatif détecté pour %s (%s)."
                    ) % (employee.name, acc.number))
    
                lines.append((0, 0, {
                    'employee_id': employee.id,
                    'bank_account_id': acc.id,
                    'libelle': acc.libelle,
                    'amount': amount,
                }))
    
        self.line_ids = lines
    # -----------------------------
    # TOTAL GENERAL
    # -----------------------------
    @api.depends('line_ids.amount')
    def _compute_total_amount(self):
        for wizard in self:
            wizard.total_amount = sum(wizard.line_ids.mapped('amount'))

    # -----------------------------
    # ACTION PRINT
    # -----------------------------
    def action_print_report(self):
        self.ensure_one()

        if not self.line_ids:
            raise ValidationError(_("Aucune ligne de virement à imprimer."))

        return self.env.ref(
            'paie_gainde.action_report_ordre_virement_hr'
        ).report_action(
            self,
            data={
                'date_start': self.date_start,
                'date_stop': self.date_stop,
            }
        )


class WizardOrdreVirementLine(models.TransientModel):
    _name = 'wizard.ordre.virement.hr.line'
    _description = 'Ligne ordre de virement'

    wizard_id = fields.Many2one(
        'wizard.ordre.virement.hr',
        ondelete='cascade'
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string="Employé",
        readonly=True
    )

    bank_account_id = fields.Many2one(
        'hr.bank.employee',
        string="Compte bancaire",
        readonly=True
    )

    libelle = fields.Selection([
        ('principal', 'Compte Principal'),
        ('subvention', 'Subvention Immobilier'),
        ('partiel', 'Virement Partiel'),
    ], string="Libellé", readonly=True)

    amount = fields.Float(
        string="Montant à virer",
        readonly=True
    )
