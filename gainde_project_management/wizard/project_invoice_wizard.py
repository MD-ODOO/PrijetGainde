from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ProjectInvoiceWizard(models.TransientModel):
    _name = 'project.invoice.wizard'
    _description = 'Facturer les Jalons du Projet'

    project_id = fields.Many2one(
        'project.project',
        string="Projet",
        required=True,
        readonly=True,
        default=lambda self: self.env.context.get('default_project_id')
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string="Bon de Commande Associé",
        compute='_compute_sale_order',
        store=False,
        readonly=True,
    )
    billing_method = fields.Selection(
        related='project_id.billing_method',
        readonly=True,
    )
    milestone_ids = fields.Many2many(
        'project.milestone',
        string="Jalons à Facturer",
        domain="[('project_id', '=', project_id), ('is_reached', '=', True), ('invoiced', '=', False)]",
        help="Sélectionnez les jalons atteints à facturer"
    )
    fixed_amount = fields.Monetary(
        string="Montant à facturer (prix fixe)",
        currency_field='currency_id',
        help="Montant total à facturer pour un prix fixe"
    )

    currency_id = fields.Many2one(
        related='project_id.currency_id',
        readonly=True,
    )
    invoice_date = fields.Date(
        string="Date de Facture",
        default=fields.Date.context_today,
        required=True
    )
    journal_id = fields.Many2one(
        'account.journal',
        string="Journal de Facture",
        domain=[('type', '=', 'sale')],
        required=True,
        default=lambda self: self.env['account.journal'].search([('type', '=', 'sale')], limit=1)
    )
    amount_total = fields.Monetary(
        string="Montant Total à Facturer",
        compute='_compute_amount_total',
        readonly=True
    )

    @api.depends('project_id')
    def _compute_sale_order(self):
        for wizard in self:
            so = self.env['sale.order'].search([
                ('project_ids', 'in', wizard.project_id.ids)
            ], limit=1)
            wizard.sale_order_id = so

    @api.depends('milestone_ids')
    def _compute_amount_total(self):
        for wizard in self:
            if wizard.billing_method == 'milestone':
                total = 0.0
                for m in wizard.milestone_ids:
                    if wizard.sale_order_id:
                        so_line = wizard.sale_order_id.order_line.filtered(
                            lambda
                                l: l.product_id.service_tracking == 'milestone'
                        )
                        if so_line:
                            total += so_line.price_subtotal * (
                                    m.percentage or 0.0) / 100.0
                wizard.amount_total = total

            elif wizard.billing_method == 'fixed':
                wizard.amount_total = wizard.fixed_amount or 0.0
            else:
                wizard.amount_total = 0.0

    def action_create_invoice(self):
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(
                _("Aucune commande de vente associée à ce projet."))

        if self.billing_method == 'milestone' and not self.milestone_ids:
            raise UserError(_("Sélectionnez au moins un jalon à facturer."))

        if self.billing_method == 'fixed' and not self.fixed_amount:
            raise UserError(
                _("Veuillez indiquer le montant pour le prix fixe."))

        # Création de l'invoice
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.sale_order_id.partner_id.id,
            'invoice_date': self.invoice_date,
            'journal_id': self.journal_id.id,
            'currency_id': self.currency_id.id,
            'invoice_origin': self.sale_order_id.name,
            'invoice_user_id': self.env.user.id,
            'company_id': self.sale_order_id.company_id.id,
        }

        invoice = self.env['account.move'].create(invoice_vals)

        if self.billing_method == 'milestone':
            for milestone in self.milestone_ids:
                # Trouver la ligne de vente liée (à adapter selon ta config)
                so_line = self.sale_order_id.order_line.filtered(
                    lambda
                        l: l.name == milestone.name or l.product_id.service_tracking == 'milestone'
                )
                if not so_line:
                    continue

                qty = milestone.percentage / 100.0 if milestone.percentage else 1.0

                self.env['account.move.line'].create({
                    'move_id': invoice.id,
                    'name': f"Jalon : {milestone.name}",
                    'quantity': qty,
                    'price_unit': so_line.price_unit,
                    'product_id': so_line.product_id.id,
                    'product_uom_id': so_line.product_uom.id,
                    'tax_ids': [(6, 0, so_line.tax_id.ids)],
                    'sale_line_ids': [(6, 0, so_line.ids)],
                    'analytic_distribution': so_line.analytic_distribution,
                })

                milestone.invoiced = True

        elif self.billing_method == 'fixed':
            so_line = self.sale_order_id.order_line.filtered(
                lambda l: l.product_id.service_tracking in [
                    'task_global_project', 'task_in_project']
            )
            if not so_line:
                raise UserError(
                    _("Aucune ligne de vente adaptée pour le prix fixe."))

            self.env['account.move.line'].create({
                'move_id': invoice.id,
                'name': f"Facturation prix fixe - {self.project_id.name}",
                'quantity': 1.0,
                'price_unit': self.fixed_amount,
                'product_id': so_line.product_id.id,
                'product_uom_id': so_line.product_uom.id,
                'tax_ids': [(6, 0, so_line.tax_id.ids)],
                'sale_line_ids': [(6, 0, so_line.ids)],
                'analytic_distribution': so_line.analytic_distribution,
            })

        invoice._onchange_invoice_line_ids()  # Recalcul taxes, total, etc.
        invoice.action_post()  # Ou laisser en draft selon besoin

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'views': [(False, 'form')],
            'target': 'current',
        }
