from odoo import api, models, fields
from num2words import num2words


class AccountInvoice(models.Model):
    _inherit = "account.move"

    amount_text = fields.Char('Montant en lettres', compute='get_amount_text') 

   # @api.multi
    @api.depends('amount_total')
    def get_amount_text(self):
        for record in self:
            number_in_word = num2words(record.amount_total, lang='fr')
            record.amount_text = number_in_word and number_in_word.capitalize()