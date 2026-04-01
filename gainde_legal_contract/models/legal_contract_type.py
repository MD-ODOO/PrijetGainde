from odoo import models, fields


class LegalContractType(models.Model):
    _name = 'legal.contract.type'
    _description = 'Type de Contrat'

    name = fields.Char(required=True)
    description = fields.Text(string="Description du type")
    code = fields.Char(string="Code interne")
    header_template = fields.Html(
        string="Modèle d'En-tête (Parties)",
        help="Utilisez {{partner_name}}, {{ninea}}, {{adresse}} comme variables."
    )
    category = fields.Selection([
        ('consultant', 'Prestataire Individuel (Personne Physique)'),
        ('business', 'Société de Prestation (Personne Morale)'),
        ('market', 'Accord de Marché / Contrat Cadre'),
        ('nda', 'Accord de Confidentialité'),
        ('protocol', 'Protocole d’accord'),
        ('insurance', 'Souscription Orbus Insurance'),
        ('bank', 'Souscription Orbus Bank'),
        ('subscription', 'Souscription'),
    ], string="Categorie du Contrat", required=True)
    template_id = fields.Many2one('ir.actions.report', string="Template PDF",
                                  domain=[('model', '=', 'legal.contract'),
                                          ('report_type', '=', 'qweb-pdf')],
                                  help="Modèle QWeb utilisé pour générer le PDF du contrat de ce type")
    active = fields.Boolean(default=True)
    article_template_ids = fields.One2many('legal.article.template',
                                           'contract_type_id',
                                           string="Articles par défaut")
