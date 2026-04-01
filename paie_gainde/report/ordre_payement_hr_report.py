# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime
from dateutil import relativedelta
import base64
import zipfile
from io import BytesIO
from io import BytesIO
import xlsxwriter



MONTHS_FR = {
    1: 'JANVIER',
    2: 'FEVRIER',
    3: 'MARS',
    4: 'AVRIL',
    5: 'MAI',
    6: 'JUIN',
    7: 'JUILLET',
    8: 'AOUT',
    9: 'SEPTEMBRE',
    10: 'OCTOBRE',
    11: 'NOVEMBRE',
    12: 'DECEMBRE',
}

class HrPayBatch(models.Model):
    _name = 'hr.pay.batch'
    _description = 'Lot de virement RH'
    _order = 'id desc'

   
    name = fields.Char(
    string="Reference",
    readonly=True,
    copy=False,
    default=lambda self: _('Nouveau'))
    
    export_zip = fields.Binary(
    string="Exports bancaires (ZIP)",
    readonly=True
    )

    export_zip_name = fields.Char(
        string="Nom du fichier ZIP",
        readonly=True
    )

    date_start = fields.Date(
        string="Date debut",
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

    bank_line_ids = fields.One2many(
        'hr.pay.batch.bank',
        'batch_id',
        string="Banques"
    )

    order_ids = fields.One2many(
        'hr.pay.order',
        'batch_id',
        string="Ordres generes",
        readonly=True
    )

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('generated', 'Genere'),
    ], default='draft')
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('Nouveau')) == _('Nouveau'):
            date_ref = vals.get('date_start') or date.today()
    
            if isinstance(date_ref, str):
                date_ref = fields.Date.from_string(date_ref)
    
            month_label = MONTHS_FR.get(date_ref.month)
            year = date_ref.year
    
            seq = self.env['ir.sequence'].next_by_code(
                'hr.pay.batch',
                sequence_date=date_ref
            ) or '0000'
    
            vals['name'] = f"LOT/{month_label}/{year}/{seq}"
    
        return super().create(vals)
    
    def action_view_employee_transfers(self):
        self.ensure_one()
    
        if not self.order_ids:
            raise ValidationError(
                "Aucun virement pour ce lot."
            )
    
        return {
            'type': 'ir.actions.act_window',
            'name': 'Virements des employes',
            'res_model': 'hr.pay.order.line',
            'view_mode': 'list,form',
            'domain': [('order_id.batch_id', '=', self.id)],
            'context': {
                'default_order_id': False,
            }
        }
    # --------------------------------
    # GENERATION MULTI-BANQUES
    # --------------------------------
    def action_generate(self):
        self.ensure_one()
    
        # ?? SI LES ORDRES EXISTENT ? REDIRECTION
        if self.order_ids:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Ordres de virement',
                'res_model': 'hr.pay.order',
                'view_mode': 'list,form',
                'domain': [('batch_id', '=', self.id)],
            }
    
        if not self.bank_line_ids:
            raise ValidationError("Veuillez ajouter au moins une banque.")
    
        payslips = self.env['hr.payslip'].search([
            ('date_from', '>=', self.date_start),
            ('date_to', '<=', self.date_stop),
            ('state', '=', 'paid'),
        ])
    
        if not payslips:
            raise ValidationError("Aucun bulletin.")
    
        employees = payslips.mapped('employee_id')
    
        all_accounts = self.env['hr.bank.employee'].search([
            ('employee_id', 'in', employees.ids)
        ])
    
        for bank_line in self.bank_line_ids:
            bank = bank_line.bank_id
    
            order = self.env['hr.pay.order'].create({
                'bank_id': bank.id,
                'batch_id': self.id,
                'date_start': self.date_start,
                'date_stop': self.date_stop,
            })
    
            bank_employees = all_accounts.filtered(
                lambda a: a.bank_id.id == bank.id
            ).mapped('employee_id')
    
            bank_payslips = payslips.filtered(
                lambda p: p.employee_id in bank_employees
            )
    
            order.payslip_ids = [(6, 0, bank_payslips.ids)]
    
            for payslip in bank_payslips:
                employee = payslip.employee_id
                net = payslip.amount_net or 0.0
    
                emp_accounts = all_accounts.filtered(
                    lambda a: a.employee_id.id == employee.id
                )
    
                # ? RÈGLE MÉTIER
                total_partiel = sum(
                    acc.amount for acc in emp_accounts
                    if acc.libelle == 'partiel'
                )
    
                if total_partiel > net:
                    raise ValidationError(
                        f"Virements partiels > net pour {employee.name}"
                    )
    
                bank_accounts = emp_accounts.filtered(
                    lambda a: a.bank_id.id == bank.id
                )
    
                for acc in bank_accounts:
                    if acc.libelle == 'principal':
                        amount = net - total_partiel
                    else:
                        amount = acc.amount
    
                    if amount <= 0:
                        continue
    
                    self.env['hr.pay.order.line'].create({
                        'order_id': order.id,
                        'employee_id': employee.id,
                        'bank_account_id': acc.id,
                        'libelle': acc.libelle,
                        'amount': amount,
                    })
    
        # ? ON MARQUE LE LOT COMME GÉNÉRÉ
        self.state = 'generated'
    
        return {
            'type': 'ir.actions.act_window',
            'name': 'Ordres de virement',
            'res_model': 'hr.pay.order',
            'view_mode': 'list,form',
            'domain': [('batch_id', '=', self.id)],
        }
    def action_reset_to_draft(self):
        self.ensure_one()
    
        # ?? Sécurite : ne pas revenir en arriere si confirme
        confirmed_orders = self.order_ids.filtered(
            lambda o: o.state not in ('draft',)
        )
        if confirmed_orders:
            raise ValidationError(
                "Impossible de revenir en arriere : "
                "certains ordres sont deja confirmes ou traites."
            )
    
        # ?? Suppression des lignes et ordres
        self.order_ids.mapped('line_ids').unlink()
        self.order_ids.unlink()
    
        # ?? Retour a l’etat initial
        self.state = 'draft'
    
        return True

    
    def action_export_bank_excels(self):
        self.ensure_one()
    
        if self.state != 'generated':
            raise ValidationError(
                "Les ordres doivent etre generes avant export."
            )
    
        if not self.order_ids:
            raise ValidationError("Aucun ordre de Virement .")
    
        buffer = BytesIO()
        workbook = xlsxwriter.Workbook(buffer)
        worksheet = workbook.add_worksheet('Ordre de virement')
    
        # ======================
        # STYLES
        # ======================
        title_fmt = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'align': 'center'
        })
    
        bank_fmt = workbook.add_format({
            'bold': True,
            'font_size': 12
        })
    
        header_fmt = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'center'
        })
    
        cell_fmt = workbook.add_format({
            'border': 1
        })
    
        money_fmt = workbook.add_format({
            'border': 1,
            'num_format': '#,##0'
        })
    
        # ======================
        # TITRE GLOBAL
        # ======================
        date_ref = self.date_start
        month_label = MONTHS_FR[date_ref.month]
        year = date_ref.year
    
        worksheet.merge_range(
            'A1:D1',
            f"ORDRE DE VIREMENT du Mois de {month_label} {year}",
            title_fmt
        )
    
        current_row = 3
    
        # ======================
        # PAR BANQUE
        # ======================
        for order in self.order_ids:
    
            if not order.line_ids:
                continue
    
            # Titre banque
            worksheet.merge_range(
                f'A{current_row}:D{current_row}',
                f"BANQUE : {order.bank_id.name}",
                bank_fmt
            )
            current_row += 2
    
            # En-têtes
            headers = ['EMPLOYE', 'NUMERO DE COMPTE', 'LIBELLE', 'MONTANT']
            for col, title in enumerate(headers):
                worksheet.write(current_row, col, title, header_fmt)
    
            current_row += 1
    
            # Lignes
            for line in order.line_ids:
                worksheet.write(current_row, 0, line.employee_id.name or '', cell_fmt)
                worksheet.write(current_row, 1, line.bank_account_id.number or '', cell_fmt)
                worksheet.write(
                    current_row, 2,
                    dict(line._fields['libelle'].selection).get(line.libelle),
                    cell_fmt
                )
                worksheet.write_number(current_row, 3, line.amount, money_fmt)
                current_row += 1
    
            # Ligne vide entre banques
            current_row += 2
    
        # Largeur colonnes
        worksheet.set_column('A:A', 25)
        worksheet.set_column('B:B', 22)
        worksheet.set_column('C:C', 20)
        worksheet.set_column('D:D', 15)
    
        workbook.close()
        buffer.seek(0)
    
        # ======================
        # SAUVEGARDE FICHIER
        # ======================
        self.export_zip = base64.b64encode(buffer.read())
        self.export_zip_name = (
            f"ORDRE_VIREMENT_{month_label}_{year}_{self.name}.xlsx"
            .replace('/', '_')
        )
    
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model=hr.pay.batch'
                   f'&id={self.id}'
                   f'&field=export_zip'
                   f'&filename={self.export_zip_name}'
                   f'&download=true',
            'target': 'self',
        }





class HrPayOrder(models.Model):
    _name = 'hr.pay.order'
    _description = 'Ordre de virement RH'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
    string="Reference",
    readonly=True,
    copy=False,
    default=lambda self: _('Nouveau')
              )
              
    batch_id = fields.Many2one(
          'hr.pay.batch',
          string="Lot de virement",
          readonly=True
      )

    bank_id = fields.Many2one(
        'res.bank',
        string="Banque",
        required=True,
        tracking=True
    )

    date_start = fields.Date(
        string="Date debut",
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

    payslip_ids = fields.Many2many(
        'hr.payslip',
        string="Bulletins de Paie",
        readonly=True
    )

    line_ids = fields.One2many(
        'hr.pay.order.line',
        'order_id',
        string="Lignes de virement",
        readonly=True
    )

    total_amount = fields.Float(
        string="Total",
        compute="_compute_total_amount",
        store=True
    )

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmer'),
    ], default='draft', tracking=True)
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('Nouveau')) == _('Nouveau'):
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'hr.pay.order'
            ) or _('Nouveau')
        return super().create(vals)


    # ----------------------------------
    # CALCUL DES VIREMENTS
    # ----------------------------------
    
    def action_compute(self):
        for order in self:
            order.line_ids.unlink()
            order.payslip_ids = [(5, 0, 0)]
    
            if not order.bank_id:
                raise ValidationError("Veuillez selectionner une banque.")
    
            employees = self.env['hr.bank.employee'].search([
                ('bank_id', '=', order.bank_id.id)
            ]).mapped('employee_id')
    
            payslips = self.env['hr.payslip'].search([
                ('employee_id', 'in', employees.ids),
                ('date_from', '>=', order.date_start),
                ('date_to', '<=', order.date_stop),
                ('state', '=', 'paid'),
            ])
            
            all_accounts = self.env['hr.bank.employee'].search([
                  ('employee_id', '=', employees.id)
              ])
    
            order.payslip_ids = [(6, 0, payslips.ids)]
            
            total_other_amount = sum(
                  acc.amount for acc in all_accounts
                  if acc.libelle != 'principal'
              )
              
    
            for payslip in payslips:
                net = payslip.amount_net or 0.0
                
                if total_other_amount > net:
                    raise ValidationError(_(
                    "Le total des virements (%s) depasse le net (%s) "
                    "pour l'employe %s."
                  ) %(total_other_amount, net, employee.name))
    
                accounts = self.env['hr.bank.employee'].search([
                    ('employee_id', '=', payslip.employee_id.id),
                    ('bank_id', '=', order.bank_id.id)
                ])
    
    
                for acc in accounts:
                    amount = acc.amount
                    if acc.libelle == 'principal':
                        amount = net - total_other_amount
    
                    if amount < 0:
                        raise ValidationError(
                            f"Montant negatif pour {payslip.employee_id.name}"
                        )
    
                    self.env['hr.pay.order.line'].create({
                        'order_id': order.id,
                        'employee_id': payslip.employee_id.id,
                        'bank_account_id': acc.id,
                        'libelle': acc.libelle,
                        'amount': amount,
                    })


    @api.depends('line_ids.amount')
    def _compute_total_amount(self):
        for order in self:
            order.total_amount = sum(order.line_ids.mapped('amount'))

    def action_confirm(self):
        self.write({'state': 'confirmed'})




class HrPayOrderLine(models.Model):
    _name = 'hr.pay.order.line'
    _description = 'Ligne ordre de virement'

    order_id = fields.Many2one(
        'hr.pay.order',
        ondelete='cascade'
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string="Employe",
        readonly=True
    )

    bank_account_id = fields.Many2one(
        'hr.bank.employee',
        string="Compte bancaire",
        readonly=True
    )

    libelle = fields.Selection([
        ('principal', 'Compte Principal'),
        ('subvention', 'Subvention Immobiliere'),
        ('partiel', 'Virement Partiel'),
    ], readonly=True)

    amount = fields.Float(
        string="Montant",
        readonly=True
    )

    # ? CHAMPS CALCULÉS (PAS related)
    bank_id = fields.Many2one(
        'res.bank',
        string="Banque",
        compute='_compute_bank_batch',
        store=True,
        readonly=True
    )

    batch_id = fields.Many2one(
        'hr.pay.batch',
        string="Lot",
        compute='_compute_bank_batch',
        store=True,
        readonly=True
    )
    
    @api.depends('order_id', 'order_id.bank_id', 'order_id.batch_id')
    def _compute_bank_batch(self):
        for line in self:
            line.bank_id = line.order_id.bank_id if line.order_id else False
            line.batch_id = line.order_id.batch_id if line.order_id else False

    


class HrPayBatchBank(models.Model):
    _name = 'hr.pay.batch.bank'
    _description = 'Banques du lot de virement'

    batch_id = fields.Many2one(
        'hr.pay.batch',
        ondelete='cascade'
    )

    bank_id = fields.Many2one(
        'res.bank',
        string="Banque",
        required=True
    )

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    # =========================
    # ENVOI INDIVIDUEL
    # =========================
    def action_send_payslip_email(self):
        template = self.env.ref(
            'payslip_email_send.email_template_payslip',
            raise_if_not_found=True
        )

        for slip in self.filtered(lambda s: s.state in ('paid', 'done')):
            email = slip.employee_id.work_email or slip.employee_id.private_email
            if not email:
                raise UserError(
                    f"Aucun email defini pour l'employe : {slip.employee_id.name}"
                )

            template.send_mail(slip.id, force_send=True)

    # =========================
    # ENVOI GROUPÉ
    # =========================
    def action_send_payslip_email_batch(self):
        template = self.env.ref(
            'payslip_email_send.email_template_payslip',
            raise_if_not_found=True
        )

        for slip in self.filtered(lambda s: s.state in ('paid', 'done')):
            email = slip.employee_id.work_email or slip.employee_id.private_email
            if email:
                template.send_mail(slip.id, force_send=True)


class OrdrePayementHRReport(models.AbstractModel):
    _name = 'report.paie_gainde.report_pay_order'
    _description = 'Report ordre de virement'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['wizard.ordre.virement.hr'].browse(docids)

        lines = []
        for line in wizard.line_ids:
            lines.append({
                'employee_name': line.employee_id.name,
                'bank_name': line.bank_account_id.bank_id.name,
                'account_number': line.bank_account_id.number,
                'libelle': line.libelle,
                'amount': line.amount,
            })

        return {
            'docs': wizard,
            'lines': lines,
            'total_amount': wizard.total_amount,
            'date_start': wizard.date_start,
            'date_stop': wizard.date_stop,
        }
