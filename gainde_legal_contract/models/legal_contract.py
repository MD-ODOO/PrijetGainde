from odoo import models, fields, api, _
from datetime import date, timedelta

from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta


class LegalContract(models.Model):
    _name = 'legal.contract'
    _description = 'Contrat Juridique'
    _inherit = ['mail.thread', 'mail.activity.mixin',
                'abstract.signable.document']
    _rec_name = 'name'
    _order = 'name desc'

    name = fields.Char(string="Référence Contrat", required=True,
                       tracking=True, default='/', readonly=True, copy=False)
    company_id = fields.Many2one('res.company', string="Entité GAINDE",
                                 required=True,
                                 default=lambda self: self.env.company)
    partner_id = fields.Many2many('res.partner', string="Co-contractant",
                                  tracking=True, required=True)
    mission_description = fields.Text(string="Description de la mission ")
    duration_text = fields.Char(string="Durée (en lettres/chiffres)")
    activity = fields.Char(string="ACTIVITE / SECTEUR")
    comments = fields.Text(string="COMMENTAIRES")
    partner_cni = fields.Char(string="CNI du prestataire physique")
    header_content = fields.Html(string="Introduction et Parties",
                                 compute='_compute_header_content', store=True,
                                 readonly=False, sanitize=False,
                                 precompute=True )
    title = fields.Char(string="Titre du contrat")
    object = fields.Char(string="Objet du contrat")
    writer = fields.Char(string="Redateur du contrat")
    version = fields.Char(string="Version du contrat")
    reference = fields.Char(string="Reference du contrat")
    diffusion = fields.Char(string="Diffusion du contrat")
    partner_role = fields.Selection([
        ('consultant', 'Consultant / Expert'),
        ('business', 'Socièté Prestataire / Fournisseur'),
        ('partner', 'Partenaire Stratégique'),
        ('subscription', 'Souscripteur / Abonné'),
        ('other', 'Autre')
    ], string="Rôle du co-contractant", compute="_compute_partner_role",
        store=True)
    company_representative_id = fields.Many2one(
        'res.users',
        string="Signataire GAINDE",
        default=lambda self: self.env.user
    )
    partner_representative_name = fields.Char(
        string="Représentant Partenaire",
        help="Nom de la personne physique qui signe pour l'entreprise adverse"
    )

    department_id = fields.Many2one('hr.department',
                                    string="Service Demandeur",
                                    default=lambda
                                            self: self.env.user.department_id)

    type_id = fields.Many2one('legal.contract.type', string="Type de Contrat",
                              tracking=True, )
    article_ids = fields.One2many('legal.article.template', 'contract_id',
                                  string="Articles du Contrat")
    contract_category = fields.Selection(related='type_id.category',
                                         store=True)

    date_start = fields.Date(string="Date de Début")
    date_end = fields.Date(string="Date d’Échéance")
    renewal_date = fields.Date(string="Date de Renouvellement")
    signature_date = fields.Date(string="Date de Signature")
    stage_id = fields.Many2one('legal.contract.stage', string="Étape",
                               tracking=True,
                               default=lambda self: self.env.ref(
                                   'gainde_legal_contract.contract_stage_draft',
                                   raise_if_not_found=False))
    stage_id_name = fields.Char(related='stage_id.name',
                                string="Nom de l'étape", store=True)

    sign_request_id = fields.Many2one('sign.request',
                                      string="Demande de Signature")

    amendment_ids = fields.One2many('legal.contract.amendment', 'contract_id',
                                    string="Avenants")

    litigation_ids = fields.One2many('legal.litigation', 'contract_id',
                                     string="Contentieux Liés")
    # 1. Personnel (Physique)
    job_id = fields.Many2one('hr.job', string="Poste")
    salary_gross = fields.Float("Salaire Mensuel Brut")
    salary_in_words = fields.Char("Salaire en toutes lettres")
    trial_period = fields.Integer("Période d'essai (jours)")

    # 2. Marché / Prestation (Morale)
    representative_name = fields.Char("Représentant Légal")
    market_value = fields.Float("Valeur Totale du Marché")
    guarantee_amount = fields.Float("Caution / Garantie")
    payment_terms = fields.Selection(
        [('30', '30 jours'), ('45', '45 jours'), ('60', '60 jours')],
        "Conditions de paiement")

    # 3. Confidentialité (NDA)
    secrecy_years = fields.Integer("Durée du secret (ans)", default=5)
    penalty_amount = fields.Float("Montant de la pénalité")

    # Preavis
    notice_type = fields.Selection([
        ('days', 'Jours'),
        ('months', 'Mois'),
    ], string="Type de préavis", default='months', required=False)

    notice_duration = fields.Integer(string="Durée du préavis", default=1)

    notice_end_date = fields.Date(
        string="Fin de préavis",
        compute='_compute_notice_end_date',
        store=True,
        readonly=True,
    )
    alert_sent = fields.Boolean(default=False)

    document_ids = fields.Many2many(
        comodel_name='ir.attachment',
        relation='legal_contract_ir_attachment_rel',
        column1='contract_id',
        column2='attachment_id',
        string="Documents Attachés",
        copy=False,
        tracking=True,
    )

    @api.depends('type_id', 'partner_id.is_company')
    def _compute_partner_role(self):
        for rec in self:
            if not rec.type_id:
                rec.partner_role = 'other'
                continue
            if rec.type_id.category == 'consultant':
                rec.partner_role = 'consultant'

            elif rec.type_id.category in ['business', 'market']:
                rec.partner_role = 'business'

            elif rec.type_id.category in ['insurance', 'bank', 'subscription']:
                rec.partner_role = 'subscription'

            elif rec.type_id.category in ['nda', 'protocol']:
                rec.partner_role = 'partner'

            else:
                rec.partner_role = 'other'

    @api.onchange('type_id')
    def _onchange_type_id(self):
        """ Copie les articles du type vers le contrat lors du choix du type """
        if self.type_id and self.type_id.article_template_ids:
            new_articles = []
            for art in self.type_id.article_template_ids:
                new_articles.append((0, 0, {
                    'sequence': art.sequence,
                    'name': art.name,
                    'content': art.content,
                }))
            self.article_ids = [(5, 0,
                                 0)] + new_articles  # On vide et on remplit

    @api.model_create_multi
    def create(self, vals_list):
        """
        Surcharge de create pour attribuer la séquence uniquement si name == '/'
        Fonctionne aussi pour la création multiple (rare mais possible via import/XML)
        """
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                dt = fields.Date.today()
                print("DATE UTILISÉE POUR LA SÉQUENCE: %s", dt)
                import logging
                _logger = logging.getLogger(__name__)
                _logger.warning("DATE UTILISÉE POUR LA SÉQUENCE: %s", dt)

                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'legal.contract', sequence_date=dt) or '/'
        return super().create(vals_list)

    def write(self, vals):
        for record in self:
            # Vérification : NI Admin, NI Juriste
            if not self.env.user.has_group(
                'gainde_legal_contract.group_ged_manager') and \
                not self.env.user.has_group(
                    'gainde_legal_contract.group_ged_juridique'):

                # On vérifie si l'étape actuelle n'est pas "Création"
                # (On teste sur le nom pour être sûr de matcher ton record XML)
                if record.stage_id.name != 'Création':
                    raise UserError(
                        _("⚠️ Accès restreint : En tant qu'Assistant, vous ne pouvez modifier un contrat que lorsqu'il est à l'étape 'Création'. \n\nContactez un Juriste ou l'Admin pour toute modification sur l'étape actuelle : %s.") % record.stage_id.name)

        return super(LegalContract, self).write(vals)

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        return self.env['legal.contract.stage'].search([])

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for record in self:
            if record.date_end and record.date_start > record.date_end:
                raise UserError(
                    _("La date de fin doit être postérieure à la date de début."))

    def action_send_for_validation(self):
        # Workflow simple : Crée activité pour validation
        self.activity_schedule('mail.mail_activity_data_todo',
                               summary=_("Valider Contrat"),
                               note=_("Veuillez valider ce contrat."),
                               user_id=self.env.user.id)
        self.stage_id = 'validation'

    def action_send_for_signature(self):
        if not self.document_ids:
            raise UserError(_("Aucun document attaché pour signature."))
        template = self.env.ref(
            'legal_contract_management.sign_template_contract',
            raise_if_not_found=False)
        if not template:
            raise UserError(
                _("Template de signature non trouvé. Créez-en un dans Sign."))
        sign_request = self.env['sign.request'].create({
            'template_id': template.id,
            'reference': self.name,
            'request_item_ids': [(0, 0, {
                'partner_id': self.partner_id.id,
                'role_id': self.env.ref('sign.sign_item_role_default').id,
                # Rôle par défaut
            })]
        })
        sign_request.action_draft()
        sign_request.action_sign()
        self.sign_request_id = sign_request
        return {
            'type': 'ir.actions.act_url',
            'url': f"/web#id={sign_request.id}&model=sign.request&view_type=form",
            'target': 'self',
        }

    @api.depends('date_end', 'notice_type', 'notice_duration')
    def _compute_notice_end_date(self):
        for contract in self:
            if not contract.date_end:
                contract.notice_end_date = False
                continue

            if contract.notice_type == 'days':
                contract.notice_end_date = contract.date_end - relativedelta(
                    days=contract.notice_duration)
            elif contract.notice_type == 'months':
                contract.notice_end_date = contract.date_end - relativedelta(
                    months=contract.notice_duration)
            else:
                contract.notice_end_date = False

    # Optionnel : alerte si on approche de la fin de préavis
    @api.model
    def _cron_check_notice_end(self):
        today = fields.Date.today()
        contracts = self.search([
            ('notice_end_date', '!=', False),
            ('notice_end_date', '<=', today + relativedelta(days=30)),
            ('stage_id.fold', '=', False),  # Pas encore clôturé
        ])
        for c in contracts:
            c.message_post(body=_(
                "Attention : fin de préavis prévue le %(date)s (dans %(days)d jours).",
                date=c.notice_end_date, days=(c.notice_end_date - today).days
            ))

    @api.model
    def _cron_alert_expirations(self):
        """ Cron de vérification des dates d'échéance """
        today = date.today()
        # Correction de la virgule à la fin qui transformait le résultat en tuple
        contracts = self.search([
            ('date_end', '<=', today + timedelta(days=30)),
            ('stage_id_name', '!=', 'Clôturé'),
            ('alert_sent', '=', False)
        ])
        for contract in contracts:
            contract.message_post(
                body=_("Alerte : le contrat %s arrive à échéance le %s.") % (
                    contract.name, contract.date_end)
            )
            contract.write({'alert_sent': True})

    # ALERTES AUTOMATIQUES
    def _cron_check_contract_alerts(self):
        today = date.today()
        contracts = self.search([
            ('date_end', '<=', today + timedelta(days=30)),
            ('alert_sent', '=', False)
        ])
        for contract in contracts:
            contract.message_post(
                body=f"Alerte : le contrat {contract.name} arrive à échéance le {contract.date_end}."
            )
            contract.alert_sent = True

    def _get_stage_by_name(self, name):
        return self.env['legal.contract.stage'].search(
            [('name', 'ilike', name)], limit=1)

    def action_set_stage_negotiation(self):
        stage = self._get_stage_by_name('Négociation')
        if stage:
            self.stage_id = stage
            self.message_post(body=_(
                "🤝 Le contrat est entré en phase de <b>Négociation</b>."))

    def action_set_stage_signed(self):
        stage = self._get_stage_by_name('Signé')
        if stage:
            self.stage_id = stage
            self.message_post(body=_(
                "✍️ <b>Contrat Signé</b>. Le document est désormais officiel."))

    def action_set_stage_execution(self):
        stage = self._get_stage_by_name('Exécution')
        if stage:
            self.stage_id = stage
            self.message_post(body=_(
                "🚀 Passage en <b>Exécution</b>. Les prestations peuvent débuter."))

    def action_set_stage_closed(self):
        stage = self.env['legal.contract.stage'].search([('fold', '=', True)],
                                                        order='sequence desc',
                                                        limit=1)
        if stage:
            self.stage_id = stage
            self.message_post(
                body=_("🏁 <b>Contrat Clôturé</b>. Dossier archivé."))

    def action_set_stage_draft(self):
        stage = self.env['legal.contract.stage'].search([], order='sequence',
                                                        limit=1)
        if stage:
            self.stage_id = stage
            self.message_post(
                body=_("📄 Remise en <b>Brouillon</b> du contrat."))

    def _update_stage_after_sign(self):
        """ Recherche l'étape 'Signé' de manière dynamique selon le modèle """
        self.ensure_one()
        if hasattr(self, 'stage_id'):
            stage_model = self.fields_get(['stage_id'])['stage_id']['relation']
            signed_stage = self.env[stage_model].search([
                ('name', 'ilike', 'Signé')
            ], limit=1)

            if signed_stage:
                self.stage_id = signed_stage

    def get_processed_articles(self):
        """ Remplace les variables dynamiques par les nouvelles données """
        self.ensure_one()
        processed_list = []

        # Formatage des dates pour le Sénégal (JJ/MM/AAAA)
        d_start = self.date_start.strftime(
            '%d/%m/%Y') if self.date_start else "__________"
        d_end = self.date_end.strftime(
            '%d/%m/%Y') if self.date_end else "Indéterminée"

        for art in self.article_ids:
            c = art.content or ""

            # --- Remplacements Identité ---
            c = c.replace('{{partner_name}}',
                          self.partner_id.name or "__________")
            c = c.replace('{{cni}}', self.partner_cni or "__________")
            c = c.replace('{{representant}}', self.representative_name or "__________")
            c = c.replace('{{ninea}}', self.partner_id.vat or "__________")

            # --- Nouveaux Remplacements ---
            c = c.replace('{{date_debut}}', d_start)
            c = c.replace('{{date_fin}}', d_end)
            c = c.replace('{{duree}}', self.duration_text or "__________")
            c = c.replace('{{mission}}',
                          self.mission_description or "__________")
            c = c.replace('{{salaire_brut}}',
                          "{:,.0f} FCFA".format(self.salary_gross or 0))
            c = c.replace('{{salaire_lettres}}',
                          self.salary_in_words or "__________")

            processed_list.append({'name': art.name, 'content': c})
        return processed_list

    @api.onchange('type_id', 'partner_id')
    def _onchange_header_content(self):
        """ Force le calcul visuel immédiat du header lors de la saisie """
        if self.type_id and self.partner_id:
            self._compute_header_content()

    @api.depends('type_id', 'partner_id', 'type_id.header_template')
    def _compute_header_content(self):
        """ Précharge l'en-tête dynamique lors du choix du type ou du partenaire """
        for rec in self:
            # Si les infos de base manquent, on ne calcule rien

            if not rec.type_id or not rec.partner_id:
                rec.header_content = ""
                continue

            # On récupère le template du type de contrat
            template = rec.type_id.header_template

            if template:
                # Logique de remplacement des variables (Placeholders)
                content = template
                content = content.replace('{{cni}}', rec.partner_cni or "__________")
                content = content.replace('{{representant}}', rec.representative_name or "__________")
                content = content.replace('{{partner_name}}',
                                          rec.partner_id.name or "__________")
                content = content.replace('{{ninea}}',
                                          rec.partner_id.vat or "__________")
                content = content.replace('{{rccm}}',
                                          rec.partner_id.company_registry or "__________")

                # Nettoyage de l'adresse pour le HTML
                addr = rec.partner_id.contact_address or "__________"
                content = content.replace('{{adresse}}',
                                          addr.replace('\n', ' '))

                rec.header_content = content
            else:
                partner_info = f"immatriculé(e) sous le RC {rec.partner_id.company_registry or '____'}, NINEA {rec.partner_id.vat or '____'}" if rec.partner_id.is_company else f"titulaire de la CNI N° {rec.partner_cni or '____'}"
                html = f"""
                        <p>Entre <strong>GAINDE 2000</strong>, GIE au capital de 300.000.000 FCFA, immatriculé sous le RC SN DKR 2002 B 1149, NINEA 0021516952G6, sis à l’Immeuble ORBUS, Dakar, Sénégal, représenté par Monsieur Ibrahima Nour Eddine DIAGNE, Administrateur Général ; <br/><strong>D’une part ;</strong></p>
                        <p>Et <strong>{rec.partner_id.name}</strong>, {partner_info}, sis à {rec.partner_id.contact_address or '____'}. <br/><strong>Ci-après dénommé « le Prestataire » ; D’autre part ;</strong></p>
                        <p><i>Ci-dessous, collectivement désignés « les Parties ».</i></p>
                        <p><strong>Il a été convenu et arrêté ce qui suit :</strong></p>
                    """
                rec.header_content = html

        # Force l'affichage immédiat à l'écran lors de la création

    # @api.onchange('type_id', 'partner_id')
    # def _onchange_type_and_partner(self):
    #     """ Précharge l'en-tête dynamique lors du choix du type ou du partenaire """
    #     if self.type_id and self.type_id.header_template and self.partner_id:
    #         content = self.type_id.header_template
    #
    #         # Remplacement des variables de base
    #         content = content.replace('{{partner_name}}',
    #                                   self.partner_id.name or "__________")
    #         content = content.replace('{{ninea}}',
    #                                   self.partner_id.x_ninea or "__________")
    #         content = content.replace('{{rccm}}',
    #                                   self.partner_id.company_registry or "__________")
    #         content = content.replace('{{adresse}}',
    #                                   self.partner_id.contact_address or "__________")
    #
    #         self.header_content = content
