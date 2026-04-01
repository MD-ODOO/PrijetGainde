from odoo import models, fields, api, _, tools
from odoo.exceptions import ValidationError, UserError
from dateutil.relativedelta import relativedelta
from datetime import timedelta, datetime
import logging

_logger = logging.getLogger(__name__)


class ProjectProject(models.Model):
    _inherit = 'project.project'

    project_type = fields.Selection(
        [('internal', 'Interne'), ('external', 'Externe'), ('poc', 'POC'), ],
        string='Type de Projet', required=True, default='internal')

    scope_description = fields.Text(string='Description du Périmètre',)
    budget_total = fields.Monetary(string='Budget Total',
                                   compute="_compute_budget_amounts",
                                   store=True, inverse="_inverse_budget_total",
                                   readonly=False, default=0.0,
                                   currency_field='currency_id', )
    is_budgetary_project = fields.Boolean(
        string="Projet budgétaire",
        default=True,
        help="Cochez si ce projet doit être suivi budgétairement (obligatoire sauf POC)."
    )
    budget_imputed = fields.Monetary(
        string="Budget Imputé",
        currency_field='currency_id',
        compute='_compute_budget_amounts',
        store=True,
        help="Budget imputé sur les lignes budgétaires liées au compte analytique."
    )

    currency_id = fields.Many2one('res.currency', default=lambda
        self: self.env.company.currency_id)

    engaged_costs = fields.Monetary(string="Coûts Engagés",
                                    compute="_compute_budget_amounts",
                                    store=True, aggregator="sum",
                                    currency_field='currency_id',
                                    help="Somme des bons de commande d'achat (PO) confirmés non encore facturés."
                                    )
    realized_costs = fields.Monetary(compute='_compute_budget_amounts',
                                     store=True,
                                     currency_field='currency_id',
                                     string='Coûts Réalisés', aggregator="sum",
                                     help="Somme des factures fournisseurs et feuilles de temps liées au compte analytique.",
                                     )
    remaining_budget = fields.Monetary(string="Budget Restant",
                                       compute="_compute_budget_amounts",
                                       store=True, aggregator="sum",
                                       currency_field='currency_id')

    billing_method = fields.Selection(
        [('timesheet', 'Temps Passés'), ('milestone', 'Jalons'),
         ('fixed', 'Prix Fixe')], string='Méthode de Facturation',
        default='milestone')

    document_folder_id = fields.Many2one('documents.document',
                                         string='Dossier Documents',
                                         compute='_compute_document_folder',
                                         store=True)
    purchase_count = fields.Integer(compute='_compute_purchase_count',
                                    string="Nombre d'achats")
    purchase_order_ids = fields.One2many('purchase.order', 'project_id',
                                         string="Commandes d'achat liées",
                                         readonly=True
                                         )
    purchase_request_count = fields.Integer(
        string="Demandes d'Achat",
        compute='_compute_purchase_request_count')
    purchase_request_ids = fields.One2many(
        'purchase.request', 'project_id',
        string="Demandes d'Achat liées"
    )
    purchase_requisition_count = fields.Integer(
        string="Demande de prix",
        compute='_compute_purchase_requisition_count')
    purchase_requisition_ids = fields.One2many(
        'purchase.requisition', 'project_id',
        string="Demande de prix liées"
    )
    department_id = fields.Many2one('hr.department', string="Département",
                                    help="Direction ou service interne responsable du projet"
                                    )
    po_ids = fields.Many2many('res.users', string="Product Owner(s)",
                              relation='project_po_rel')
    director_project_ids = fields.Many2many('res.users',
                                            string="Directeur(s) de projet",
                                            relation='project_directeur_rel')
    sponsor_ids = fields.Many2many('res.users', string="Sponsor(s)",
                                   relation='project_sponsor_rel')
    resp_tech_ids = fields.Many2many('res.users',
                                     string="Responsable(s) Technique",
                                     relation='project_tech_rel')
    tech_lead_ids = fields.Many2many('res.users', string="Tech Lead(s)",
                                     relation='project_techlead_rel')
    dev_ids = fields.Many2many('res.users', string="Développeur(s)",
                               relation='project_dev_rel')
    resp_methodo_ids = fields.Many2many('res.users',
                                        string="Resp. Méthodologie",
                                        relation='project_methodo_rel')
    spi = fields.Float(string="SPI (Schedule Performance Index)",
                       compute='_compute_spi_cpi', store=True,
                       group_operator='avg',
                       digits=(16, 2)
                       )

    cpi = fields.Float(string="CPI (Cost Performance Index)",
                       compute='_compute_spi_cpi',
                       store=True,
                       group_operator='avg',
                       digits=(16, 2)
                       )

    spi_status = fields.Selection([('green', 'Bon'), ('yellow', 'Attention'),
                                   ('red', 'Critique'), ], string="Statut SPI",
                                  compute='_compute_status', store=True)

    cpi_status = fields.Selection([('green', 'Bon'), ('yellow', 'Attention'),
                                   ('red', 'Critique'), ], string="Statut CPI",
                                  compute='_compute_status', store=True)
    planned_value = fields.Float(string="Valeur planifiée (PV)",
                                 compute='_compute_planned_value',
                                 store=True,
                                 help="Valeur planifiée : pourcentage temps écoulé × budget total"
                                 )

    earned_value = fields.Float(
        string="Valeur acquise (EV)",
        compute='_compute_earned_value',
        store=True,
        help="Valeur acquise : pourcentage avancement × budget total"
    )
    eac = fields.Monetary(
        string="Coût Final Estimé (EAC)",
        compute='_compute_projections',
        currency_field='currency_id',
        store=True,
        help="Estimation à l'achèvement : Budget Total / CPI"
    )

    vac = fields.Monetary(
        string="Écart Final (VAC)",
        compute='_compute_projections',
        currency_field='currency_id',
        store=True,
        help="Différence entre Budget Total et EAC (Négatif = Dépassement)"
    )

    estimated_end_date = fields.Date(
        string="Fin Estimée (Réelle)",
        compute='_compute_projections',
        store=True,
        help="Date de fin calculée selon le retard (SPI)"
    )

    delay_days = fields.Integer(
        string="Retard (Jours)",
        compute='_compute_projections',
        store=True
    )
    spreadsheet_id = fields.Many2one('spreadsheet.dashboard',
                                     string="Spreadsheet Dashboard",
                                     readonly=True,
                                     copy=False
                                     )
    spreadsheet_count = fields.Integer(compute='_compute_spreadsheet_count',
                                       string="Tableau de bord"
                                       )

    @api.constrains('project_type', 'account_id')
    def _check_analytic_account_required(self):
        """
        Vérifie que les projets non-POC ont un compte analytique assigné.
        """
        for project in self:
            if project.project_type != 'poc' and not project.account_id:
                raise ValidationError(
                    _("Un compte analytique est obligatoire pour les projets de type '%s'.")
                    % dict(project._fields['project_type'].selection).get(
                        project.project_type)
                )

    # @api.constrains('budget_total', 'date_start', 'date',
    #                 'is_budgetary_project')
    # def _check_poc_constraints(self):
    #     """Contrainte liée au budget selon le type de projet"""
    #     # On saute complètement la vérification en mode installation / upgrade / import
    #     if self.env.context.get('install_mode') \
    #         or self.env.context.get('skip_check') \
    #         or self.env.context.get('no_budget_check') \
    #         or self.env.context.get(
    #         'module') == self._module:  # sécurité supplémentaire
    #         return
    #
    #     for project in self:
    #         if project.project_type == 'poc':
    #             continue
    #
    #         if not project.is_budgetary_project:
    #             continue
    #
    #         # Sécurité supplémentaire : on ne bloque pas si l'enregistrement n'est pas encore flushé
    #         if not project.id or isinstance(project.id, models.NewId):
    #             continue
    #
    #         if not project.budget_total or project.budget_total <= 0:
    #             raise ValidationError(
    #                 "Le budget est obligatoire pour les projets non-POC.")
    #
    #         if not project.date_start or not project.date:
    #             raise ValidationError(
    #                 "Les dates de début et de fin sont obligatoires pour les projets budgétaires.")

    @api.depends('budget_total')
    def _inverse_budget_total(self):
        """ Mise à jour du budget analytique / ligne budgétaire """
        for project in self:
            # Protection anti-récursion + skip si contexte
            if self.env.context.get(
                'skip_inverse_budget') or not project.is_budgetary_project or not project.account_id:
                continue

            budget_analytic = self.env['budget.analytic'].sudo().search([
                ('name', '=', project.name),
                ('company_id', '=', project.company_id.id)
            ], limit=1)
            dept_id = project.department_id.id or self.env.user.department_id.id

            if not budget_analytic:
                budget_analytic = self.env['budget.analytic'].sudo().create({
                    'name': project.name,
                    'date_from': project.date_start or fields.Date.today(),
                    'date_to': project.date or fields.Date.today(),
                    'company_id': project.company_id.id,
                    'department_id': dept_id,
                    'budget_type': 'both',
                })

            line = self.env['budget.line'].sudo().search([
                ('budget_analytic_id', '=', budget_analytic.id),
                ('account_id', '=', project.account_id.id)
            ], limit=1)

            vals = {'budget_amount': project.budget_total or 0.0}

            if line:
                line.sudo().write(vals)
            else:
                vals.update({
                    'budget_analytic_id': budget_analytic.id,
                    'name': f"Budget {project.name}",
                    'account_id': project.account_id.id,
                })
                self.env['budget.line'].sudo().create(vals)

    @api.model_create_multi
    def create(self, vals_list):
        today = fields.Date.today()
        today_str = today.strftime('%Y-%m-%d')

        # ────────────────────────────────────────────────
        # 1. Préparation des valeurs AVANT création
        # ────────────────────────────────────────────────
        for vals in vals_list:
            # Garantir un nom valide
            name = vals.get('name', '').strip()
            if not name:
                vals['name'] = f"Projet {today_str}"

            # En mode installation / import → skip budget
            if self.env.context.get('install_mode'):
                vals['is_budgetary_project'] = False
                vals.setdefault('budget_total', 0.0)
                vals.setdefault('date_start', today)
                vals.setdefault('date', today)

        # ────────────────────────────────────────────────
        # 2. Création des projets
        # ────────────────────────────────────────────────
        projects = super().create(vals_list)

        # ────────────────────────────────────────────────
        # 3. Plan analytique commun (une seule recherche)
        # ────────────────────────────────────────────────
        plan = self.env['account.analytic.plan'].sudo().search([], limit=1)
        if not plan:
            plan = self.env['account.analytic.plan'].sudo().create({
                'name': 'Plan Projets Automatique',
            })

        # ────────────────────────────────────────────────
        # 4. Post-traitement : compte analytique + ligne budgétaire
        # ────────────────────────────────────────────────
        for project in projects:
            if project.project_type == 'poc':
                continue  # Pas de compte ni de budget pour POC

            # Création ou liaison du compte analytique
            if not project.account_id:
                analytic_name = (
                    project.name or f"Projet {project.id} {today_str}").strip()
                if not analytic_name:
                    analytic_name = f"Compte projet {project.id}"

                analytic = self.env['account.analytic.account'].sudo().create({
                    'name': analytic_name,
                    'plan_id': plan.id,
                    'company_id': project.company_id.id or self.env.company.id,
                    'code': f"PRJ-{project.id}",
                })

                project.sudo().write({'account_id': analytic.id})

            # Création automatique de la ligne budgétaire si projet budgétaire
            if project.is_budgetary_project:
                budget_analytic = self.env['budget.analytic'].sudo().search([
                    ('name', '=', project.name),
                    ('company_id', '=', project.company_id.id)
                ], limit=1)

                if not budget_analytic:
                    budget_analytic = self.env[
                        'budget.analytic'].sudo().create({
                        'name': project.name,
                        'date_from': project.date_start or today,
                        'date_to': project.date or today,
                        'company_id': project.company_id.id,
                        'department_id': project.department_id.id,
                        'budget_type': 'both',
                    })

                # Vérifie si une ligne existe déjà pour ce compte
                line = self.env['budget.line'].sudo().search([
                    ('budget_analytic_id', '=', budget_analytic.id),
                    ('account_id', '=', project.account_id.id)
                ], limit=1)

                vals = {
                    'budget_amount': project.budget_total or 0.0,
                    'name': f"Budget initial du projet {project.name}",
                    'account_id': project.account_id.id,
                    'budget_analytic_state': 'confirmed',
                }

                if line:
                    line.sudo().write(vals)
                else:
                    vals['budget_analytic_id'] = budget_analytic.id
                    self.env['budget.line'].sudo().create(vals)

        return projects

    @api.depends('account_id', 'is_budgetary_project')
    def _compute_budget_amounts(self):
        """
    Calcul des montants basés sur les lignes budgétaires du compte analytique :
    - budget_total : Somme des budget_amount
    - engaged_costs : Somme des committed_amount
    - realized_costs : Somme des achieved_amount
    - remaining_budget : Différence entre total et consommés
    """
        for project in self:
            budget_total = 0.0
            engaged_costs = 0.0
            realized_costs = 0.0

            # On vérifie si account_id existe pour éviter les erreurs au chargement
            if project.is_budgetary_project and project.account_id:
                # Utilisation du champ natif que vous avez listé précédemment
                lines = self.env['budget.line'].sudo().search([
                    ('account_id', '=', project.account_id.id)
                ])

                if lines:
                    budget_total = sum(lines.mapped('budget_amount'))
                    engaged_costs = sum(lines.mapped('committed_amount'))
                    realized_costs = sum(lines.mapped('achieved_amount'))

            project.budget_total = budget_total
            project.engaged_costs = engaged_costs
            project.realized_costs = realized_costs
            project.remaining_budget = budget_total + (
                engaged_costs + realized_costs)
            project.budget_imputed = engaged_costs + realized_costs

    @api.onchange('budget_total')
    def _onchange_budget_total(self):
        """
       Si on modifie manuellement le budget sur le projet,
       on répercute sur la ligne budgétaire principale.

       """

        for project in self:
            if project.account_id and project.account_id.budget_line_ids:
                # On prend la première ligne (le budget initial)
                line = project.account_id.budget_line_ids[0]
                line.budget_amount = project.budget_total

    def action_invoice_project(self):
        """ Wizard pour générer invoice basé sur méthode de paiement """
        self.ensure_one()

        if self.billing_method == 'timesheet':
            # Utilise l'action native de sale_timesheet
            action = self.env.ref(
                'sale_timesheet.project_timesheet_invoice_action').read()[
                0]
            action['context'] = dict(action.get('context', {}),
                                     active_id=self.id)
            return action

        elif self.billing_method in ['milestone', 'fixed']:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'project.invoice.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_project_id': self.id,
                            'default_sale_order_id': self.sale_order_id.id if self.sale_order_id else False,
                            },
            }
        else:
            raise UserError(
                _("Méthode de facturation non configurée pour ce projet."))

    @api.depends('name')
    def _compute_document_folder(self):
        """ Lié Chaque projet à un document"""
        for project in self:
            if 'documents.document' not in self.env:
                project.document_folder_id = self.env['documents.document']
                continue

            folder = self.env['documents.document'].search([
                ('name', '=', project.name),
                ('company_id', '=', project.company_id.id),
                ('type', '=', 'folder')
            ], limit=1)

            if not folder and project.name:
                folder = self.env['documents.document'].create({
                    'name': project.name,
                    'company_id': project.company_id.id,
                    'type': 'folder',
                })

            project.document_folder_id = folder

    # @api.onchange('project_type')
    # def _onchange_project_type(self):
    #     """ Mapping des descriptions par défaut en fonction du type de projet """
    #
    #     descriptions = {
    #         'poc': _(
    #             "Périmètre élastique pour POC – à définir itérativement."),
    #         'internal': _("Périmètre du projet interne – à définir."),
    #         'external': _(
    #             "Périmètre du projet client – à définir avec le client."),
    #     }
    #
    #     # Liste de toutes les descriptions par défaut possibles pour comparaison
    #     all_defaults = list(descriptions.values()) + [
    #         _("Périmètre du projet – à définir.")]
    #
    #     for project in self:
    #         if not project.project_type:
    #             continue
    #
    #         # 1. Gestion spécifique pour le POC
    #         if project.project_type == 'poc':
    #             project.budget_total = 0.0
    #             project.date_start = False
    #             project.date = False
    #
    #         # On ne change la description que si elle est vide
    #         current_desc = project.scope_description
    #         if not current_desc or current_desc in all_defaults:
    #             project.scope_description = descriptions.get(
    #                 project.project_type, current_desc)

    def _compute_purchase_count(self):
        """ Lignes d'achat liées à ce projet """
        for project in self:
            project.purchase_count = self.env['purchase.order'].search_count([
                ('project_id', '=', project.id)
            ])

    def action_view_purchases(self):
        self.ensure_one()
        return {
            'name': 'Achats du Projet',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('order_line.project_id', '=', self.id)],
            'context': {
                'default_project_id': self.id,
                'search_default_project_id': self.id,
            },
            'target': 'current',
        }

    def _compute_purchase_requisition_count(self):
        """ Compteur des demandes de prix liées au projet """
        for project in self:
            project.purchase_requisition_count = len(
                project.purchase_requisition_ids)

    def action_create_purchase_requisition(self):
        """ Action pour créer une nouvelle demande de prix pré-remplie RFQ """
        self.ensure_one()

        # 1. On prépare la distribution analytique pour les lignes
        # Format Odoo 18 : {'ID_COMPTE': 100}
        analytic_distrib = {}
        if self.account_id:
            analytic_distrib = {str(self.account_id.id): 100.0}

        # 2. On prépare le contexte pour pré-remplir le formulaire
        ctx = {
            'default_origin': self.name,
            'default_company_id': self.company_id.id or self.env.company.id,
            # On pré-remplit une ligne avec l'analytique du projet
            'default_order_line': [(0, 0, {
                'name': f"Achat pour {self.name}",
                'product_qty': 1.0,
                'price_unit': 0.0,
                'date_planned': fields.Datetime.now(),
                'analytic_distribution': analytic_distrib,
            })],
        }

        # Si le projet a un partenaire, on le met par défaut
        if self.partner_id:
            ctx['default_partner_id'] = self.partner_id.id

        # Si tu as un champ project_id sur purchase.order
        if 'project_id' in self.env['purchase.order']._fields:
            ctx['default_project_id'] = self.id

        return {
            'name': "Nouvelle Demande de Prix (RFQ)",
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'context': ctx,  # C'est ici que la magie opère
            'target': 'current',
        }

    def action_view_purchase_requisitions(self):
        """ Action pour voir la liste des demandes de prix liées au projet """
        self.ensure_one()
        try:
            action = \
                self.env.ref('purchase.purchase_requisition_action').read()[0]
        except ValueError:
            action = self.env["ir.actions.actions"]._for_xml_id(
                "purchase_requisition.action_purchase_requisition")

        action['domain'] = [('project_id', '=', self.id)]

        new_context = dict(self.env.context)
        new_context.update({
            'default_project_id': self.id,
            'default_company_id': self.company_id.id,
            'search_default_project_id': self.id,
        })
        action['context'] = new_context
        return action

    def _compute_purchase_request_count(self):
        """ Compteur des demandes d'achat liées au projet """
        for project in self:
            project.purchase_request_count = len(
                project.purchase_request_ids)

    def action_create_purchase_request(self):
        """ Crée une demande d'achat (purchase.request) liée au projet """
        self.ensure_one()

        # 1. Préparation des valeurs pour l'en-tête de la demande
        # On vérifie si le modèle existe avant pour éviter les crashs si le module est désinstallé
        if 'purchase.request' not in self.env:
            raise UserError(
                "Le module de Demande d'Achat (purchase_request) n'est pas installé.")

        vals = {
            'origin': self.name,
            'description': f"Besoin pour le projet : {self.name}",
            'requested_by': self.env.user.id,
            'company_id': self.company_id.id or self.env.company.id,
            'date_start': fields.Date.today(),
            # Si vous avez ajouté le champ project_id sur le modèle purchase.request
            'project_id': self.id if 'project_id' in self.env[
                'purchase.request']._fields else False,
        }

        # 2. Création de la Demande d'Achat
        purchase_request = self.env['purchase.request'].sudo().create(vals)

        # 3. Création d'une ligne de demande avec l'analytique du projet
        if self.account_id:
            self.env['purchase.request.line'].sudo().create({
                'request_id': purchase_request.id,
                'name': f"Articles pour {self.name}",
                'product_qty': 1.0,
                'date_required': fields.Date.today(),
                # Imputation analytique Odoo 18 (Mixin)
                'analytic_distribution': {str(self.account_id.id): 100.0},
            })

        # 4. Redirection vers la vue formulaire de la demande créée
        return {
            'name': "Demande d'Achat Projet",
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.request',
            'res_id': purchase_request.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_project_id': self.id,
                'default_analytic_account_id': self.account_id.id,
                'edit': True,
            }

        }

    def action_view_purchase_request(self):
        """ Action pour voir la liste des demandes d'achat liées au projet """
        self.ensure_one()
        try:
            action = self.env["ir.actions.actions"]._for_xml_id(
                "purchase_request.purchase_request_form_action")
        except ValueError:
            raise UserError(
                "L'action technique 'purchase_request.purchase_request_form_action' est introuvable."
                " Vérifiez que le module OCA purchase_request est bien installé.")

        action['domain'] = [('project_id', '=', self.id)]

        new_context = dict(self.env.context)
        new_context.update({
            'default_project_id': self.id,
            'default_company_id': self.company_id.id,
            'search_default_project_id': self.id,
        })
        action['context'] = new_context
        return action

    @api.onchange('project_type')
    def _onchange_project_type_partner(self):
        """change le client lorque le type de projet change"""
        if self.project_type != 'external':
            return {'domain': {'department_id': []}}
        else:
            self.department_id = False
            return {'domain': {'partner_id': [('is_company', '=', True)]}}

    @api.depends('spreadsheet_id')
    def _compute_spreadsheet_count(self):
        for project in self:
            project.spreadsheet_count = 1 if project.spreadsheet_id else 0

    def action_open_spreadsheet(self):
        """ menu action spreadsheet """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'spreadsheet.dashboard',
            'view_mode': 'dashboard',
            'res_id': self.spreadsheet_id.id,
            'target': 'new',
            'context': {'active_id': self.id, 'res_id': self.id,
                        'res_model': 'project.project'}
        }

    @api.depends('date_start', 'date', 'budget_total')
    def _compute_planned_value(self):
        today = fields.Date.today()
        for project in self:
            if not project.date_start or not project.date or not project.budget_total:
                project.planned_value = 0.0
                continue

            total_days = (project.date - project.date_start).days or 1
            elapsed_days = (today - project.date_start).days
            progress_time = max(0, min(1, elapsed_days / total_days))
            project.planned_value = progress_time * project.budget_total

    @api.depends('task_ids.stage_id', 'budget_total')
    def _compute_earned_value(self):
        for project in self:
            if not project.budget_total or not project.task_ids:
                project.earned_value = 0.0
                continue

            total_tasks = len(project.task_ids)
            completed_tasks = len(
                project.task_ids.filtered(lambda t: t.stage_id and (
                    getattr(t.stage_id, 'closed',
                            False) or t.stage_id.fold)))
            progress = completed_tasks / total_tasks if total_tasks else 0.0
            project.earned_value = progress * project.budget_total

    def _get_status_color(self, value):
        if value >= 1.0:
            return 'green'
        elif 0.8 <= value < 1.0:
            return 'yellow'
        else:
            return 'red'

    @api.depends('budget_total', 'realized_costs', 'engaged_costs',
                 'allocated_hours')
    def _compute_spi_cpi(self):
        for p in self:
            # Initialisation par défaut pour éviter les divisions par zéro
            if not p.budget_total or p.budget_total <= 0:
                p.cpi = 1.0
                p.spi = 1.0
                p.spi_status = 'green'
                p.cpi_status = 'green'
                continue

            # --- CALCUL DU PV (Planned Value) ---
            # Dans un calcul EVM standard, le PV est le budget prévu à date.
            # Ici on utilise le budget total comme base de référence.
            planned_value = p.budget_total

            # --- CALCUL DE L'EV (Earned Value) ---
            # On utilise milestone_progress (ex: 50.0 pour 50%)
            progress_factor = (p.milestone_progress / 100.0)
            earned_value = planned_value * progress_factor

            # --- CALCUL DE l'AC (Actual Cost) ---
            # On utilise les coûts réalisés (on s'assure que c'est positif)
            actual_cost = abs(p.realized_costs)

            # --- CALCUL DES INDEX ---
            # SPI = EV / PV
            p.spi = earned_value / planned_value if planned_value > 0 else 1.0

            # CPI = EV / AC
            if actual_cost > 0:
                p.cpi = earned_value / actual_cost
            else:
                # Si aucun coût n'est encore réalisé mais qu'on a avancé (EV > 0), le CPI est excellent (>1)
                p.cpi = 2.0 if earned_value > 0 else 1.0

            # --- MISE À JOUR DES STATUTS ---
            p.spi_status = self._get_status_color(p.spi)
            p.cpi_status = self._get_status_color(p.cpi)

    @api.depends('spi', 'cpi')
    def _compute_status(self):
        template = self.env.ref(
            'gainde_project_management.email_template_project_performance_critical',
            raise_if_not_found=False)
        for p in self:
            # Seuils classiques EVM
            old_spi_status = p.spi_status
            old_cpi_status = p.cpi_status
            p.spi_status = 'green' if p.spi >= 0.95 else 'yellow' if p.spi >= 0.85 else 'red'
            p.cpi_status = 'green' if p.cpi >= 0.95 else 'yellow' if p.cpi >= 0.85 else 'red'

            if p.spi_status == 'red' and old_spi_status != 'red':
                p.message_post(body="⚠️ Alerte : Le SPI est devenu critique !",
                               subtype_xmlid="mail.mt_note")

            # Si un des indicateurs devient 'red' alors qu'il ne l'était pas
            if (p.spi_status == 'red' and old_spi_status != 'red') or (
                p.cpi_status == 'red' and old_cpi_status != 'red'):
                if template and p.director_project_ids:
                    # Envoi immédiat de l'email aux Directeurs
                    p.with_context(
                        force_send=True).message_post_with_source(
                        source_ref=template,
                        render_values={'object': p},
                        subtype_xmlid='mail.mt_note',
                    )
            if (p.spi_status == 'red' and old_spi_status != 'red') or (
                p.cpi_status == 'red' and old_cpi_status != 'red'):
                # --- 1. Notification Push (Mobile & Bureau) ---
                p.env['bus.bus']._sendone(p.user_id.partner_id,
                                          'simple_notification', {
                                              'title': "⚠️ Alerte Projet Critique",
                                              'message': f"Le projet {p.name} est en zone rouge (SPI: {p.spi:.2f})",
                                              'sticky': True,
                                              'warning': True,
                                          })

    # def _get_stat_buttons(self):
    #     buttons = super()._get_stat_buttons()
    #
    #     p = self[:1]
    #     if p:
    #         buttons.append({
    #             'icon': 'fa-bar-chart',
    #             'text': f"SPI: {p.spi:.2f} | CPI: {p.cpi:.2f}",
    #             'number': p.spi_status.capitalize() if p.spi_status else 'N/A',
    #             'action_type': 'object',
    #             'name': 'action_view_tasks',
    #             'show': True,
    #             'sequence': 1,
    #         })
    #     return buttons

    def _create_performance_update(self):
        for project in self:
            self.env['project.update'].create({
                'project_id': project.id,
                'name': f"Bilan Performance - {fields.Date.today()}",
                'status': project.spi_status,
                # Utilise votre calcul (green, yellow, red)
                'description': f"""
                    <ul>
                        <li><b>Indice de performance planning (SPI) :</b> {project.spi}</li>
                        <li><b>Indice de performance coûts (CPI) :</b> {project.cpi}</li>
                    </ul>
                    <p>Le projet est actuellement en statut <b>{project.spi_status}</b>.</p>
                """,
                'user_id': project.user_id.id or self.env.user.id,
            })

    @api.model
    def _cron_generate_weekly_performance_reports(self):
        # Récupérer tous les projets en cours
        projects = self.search(
            [('active', '=', True), ('is_favorite', '=', True)])
        for project in projects:
            # On utilise la logique de création de bilan vue précédemment
            self.env['project.update'].create({
                'project_id': project.id,
                'name': f"Bilan Hebdomadaire Performance - {fields.Date.today()}",
                'status': project.spi_status,
                'description': f"""
                    <p>Voici le rapport de performance automatisé :</p>
                    <ul>
                        <li><b>SPI (Planning) :</b> {project.spi:.2f}
                            <span style="color: {project.spi_status}">({project.spi_status})</span></li>
                        <li><b>CPI (Coûts) :</b> {project.cpi:.2f}
                            <span style="color: {project.cpi_status}">({project.cpi_status})</span></li>
                    </ul>
                """,
                'user_id': project.user_id.id or self.env.ref(
                    'base.user_admin').id,
            })

    @api.depends('budget_total', 'cpi', 'spi', 'date_start', 'date')
    def _compute_projections(self):
        for project in self:
            # 1. Projection Financière (EAC)
            if project.cpi > 0:
                project.eac = project.budget_total / project.cpi
            else:
                project.eac = project.budget_total
            project.vac = project.budget_total - project.eac

            # 2. Projection Temporelle (Estimated End Date)
            if project.date_start and project.date:
                # Calcul de la durée initiale prévue
                duration = (project.date - project.date_start).days

                if project.spi > 0:
                    # On ajuste la durée par l'indice de performance planning
                    # Exemple: SPI de 0.5 double la durée restante
                    estimated_duration = duration / project.spi
                    project.estimated_end_date = project.date_start + timedelta(
                        days=int(estimated_duration))
                else:
                    project.estimated_end_date = project.date

                # Calcul de l'écart en jours
                project.delay_days = (
                        project.estimated_end_date - project.date).days
            else:
                project.estimated_end_date = False
                project.delay_days = 0

    @api.model
    def _cron_generate_periodic_report(self, report_type='Weekly'):
        """ Génère un bilan auto : report_type peut être 'Hebdomadaire' ou 'Mensuel' """
        projects = self.search([('active', '=', True), ('user_id', '!=', False)])
        template = self.env.ref(
            'gainde_project_management.email_template_project_periodic_report')
        for project in projects:
            # Construction du contenu HTML enrichi
            description = f"""
                <div class="o_project_update_content">
                    <h4>Bilan {report_type} - {datetime.now().strftime('%B %Y')}</h4>
                    <ul>
                        <li><strong>Indice Délais (SPI) :</strong> {project.spi:.2f}</li>
                        <li><strong>Indice Coûts (CPI) :</strong> {project.cpi:.2f}</li>
                        <li><strong>Atterrissage (EAC) :</strong> {project.eac:.2f} {project.currency_id.symbol}</li>
                        <li><strong>Progression :</strong> {project.milestone_progress}%</li>
                        <li><strong>Retard actuel :</strong> {project.delay_days} jours</li>
                    </ul>
                </div>
            """

            # Création de la Project Update (apparaît dans le dashboard)
            self.env['project.update'].create({
                'project_id': project.id,
                'name': f"Bilan {report_type} - {datetime.now().strftime('%d/%m/%Y')}",
                'status': 'on_track' if project.spi >= 1 and project.cpi >= 1 else 'at_risk',
                'description': description,
                'date': fields.Date.today(),
                'user_id': project.user_id.id or self.env.user.id,
            })
            if template:
                # On passe le type de rapport (Hebdo/Mensuel) dans le contexte pour l'email
                template.with_context(report_type=report_type).send_mail(
                    project.id,
                    force_send=True
                )

    # Option : alerte si dépassement
    # @api.constrains('budget_total', 'realized_costs')
    # def _check_budget_not_exceeded(self):
    #     for project in self:
    #         if project.realized_costs > project.budget_total:
    #             raise ValidationError(
    #                 _("Les coûts réalisés (%s) dépassent le budget total (%s) du projet %s !")
    #                 % (project.realized_costs, project.budget_total, project.name)
    #             )
    #
    #
