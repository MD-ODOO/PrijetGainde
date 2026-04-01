from odoo import models, fields


class TreasuryInvoiceTemplate(models.Model):
    _name = "treasury.invoice.template"
    _description = "Modèle de facture client"

    name = fields.Char(required=True, string="Nom")
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    partner_id = fields.Many2one("res.partner", string="Client")
    journal_id = fields.Many2one(
        "account.journal",
        string="Journal",
        domain="[('type','=','sale')]",
    )
    payment_term_id = fields.Many2one("account.payment.term", string="Conditions de paiement")
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )
    line_ids = fields.One2many("treasury.invoice.template.line", "template_id", string="Lignes")

    def action_create_invoice(self):
        self.ensure_one()
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner_id.id,
            "journal_id": self.journal_id.id,
            "invoice_payment_term_id": self.payment_term_id.id,
            "invoice_line_ids": [
                (0, 0, {
                    "product_id": line.product_id.id,
                    "name": line.name or line.product_id.display_name,
                    "quantity": line.quantity,
                    "price_unit": line.price_unit,
                    "tax_ids": [(6, 0, line.tax_ids.ids)],
                })
                for line in self.line_ids
            ],
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": move.id,
        }
