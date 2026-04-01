from odoo import models, api


class Message(models.Model):
    _inherit = 'mail.message'

    @api.model_create_multi
    def create(self, values_list):
        mail_reason_body = self._context.get('mail_reason_body')
        if isinstance(mail_reason_body, str):
            for values in values_list:
                if 'body' in values:
                    values['body'] += mail_reason_body
                else:
                    values['body'] = mail_reason_body
        return super(Message, self).create(values_list)
