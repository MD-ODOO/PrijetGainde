from odoo import models, fields


class LegalArticleTemplate(models.Model):
    _name = 'legal.article.template'
    _description = 'Articles Standards par Type'
    _order = 'sequence'

    sequence = fields.Integer(default=10)
    name = fields.Char(string="Titre de l'Article",
                       required=True)  # Ex: Article 1 : OBJET
    content = fields.Html(string="Contenu Juridique", required=True)
    contract_type_id = fields.Many2one('legal.contract.type',
                                       string="Type de Contrat",
                                       ondelete='cascade')
    contract_id = fields.Many2one('legal.contract',
                                  string="Contrat spécifique",
                                  ondelete='cascade')
