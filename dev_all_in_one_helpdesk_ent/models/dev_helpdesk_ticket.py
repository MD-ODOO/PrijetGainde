# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#s
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import fields, models,api,_
from odoo.exceptions import ValidationError
from bs4 import BeautifulSoup

class dev_helpdesk_ticket(models.Model):
    _inherit = 'helpdesk.ticket'
    
    # Nouveau champ pour le type de réclamation
    ticket_type_id = fields.Many2one(
        'helpdesk.ticket.type',
        string='Réclamations',
        tracking=True,
        index=True
    )
    
    # Champ calculé pour afficher le type de réclamation
    type_reclamation_display = fields.Char(
        string='Type de réclamation',
        compute='_compute_type_reclamation_display',
        readonly=True
    )
    
    # Surcharge du champ name pour le rendre lié au type de réclamation
    name = fields.Char(
        string='Subject',
        required=True,
        index=True,
        tracking=True,
        compute='_compute_name_from_type',
        store=True,
        readonly=False
    )
    
    # Surcharge du champ team_id pour filtrer les équipes avec profil helpdesk
    team_id = fields.Many2one(
        'helpdesk.team',
        string='Équipe',
        domain="[('profile_id.profile_type', 'in', ['helpdesk_level1', 'helpdesk_level2_functional', 'helpdesk_level2_technical', 'helpdesk_manager'])]",
        tracking=True
    )
    
    @api.depends('ticket_type_id', 'ticket_type_id.reclamations')
    def _compute_name_from_type(self):
        """Remplit automatiquement le champ name avec la réclamation sélectionnée"""
        for ticket in self:
            if ticket.ticket_type_id and ticket.ticket_type_id.reclamations:
                ticket.name = ticket.ticket_type_id.reclamations
            elif not ticket.name:
                ticket.name = ''
    
    @api.depends('ticket_type_id', 'ticket_type_id.type_reclamation')
    def _compute_type_reclamation_display(self):
        """Récupère automatiquement le type de réclamation depuis le ticket_type_id"""
        for ticket in self:
            if ticket.ticket_type_id and ticket.ticket_type_id.type_reclamation:
                ticket.type_reclamation_display = ticket.ticket_type_id.type_reclamation
            else:
                ticket.type_reclamation_display = ''
    
    task_count = fields.Integer(string='Task Count', compute='_get_task_count')
    date_deadline = fields.Date('Expected Closing', tracking=1)
    source_id = fields.Many2one('dev.helpdesk.source', string='Source')
    numero_orbus = fields.Char(string='Numéro Orbus', tracking=True, copy=False)
    partner_company_name = fields.Char(
        string='Société',
        related='partner_id.commercial_partner_id.name',
        store=True,
        readonly=True,
    )
    signature_name = fields.Char(string='Full Name', tracking=True,copy=False)
    signature_date = fields.Datetime(string='Signature Date', tracking=True , copy=False)
    signature =  fields.Binary(string='Signature' , copy=False)
    user_id=fields.Many2one('res.users',string='Assigned to',required=True)
    allowed_user_ids = fields.Many2many(
        'res.users',
        'helpdesk_ticket_allowed_users_rel',
        'ticket_id',
        'user_id',
        string='Utilisateurs autorisés',
        compute='_compute_allowed_user_ids',
        store=False,
        help="Utilisateurs ayant le profil correspondant à l'équipe sélectionnée"
    )
    lead_count = fields.Integer(string='Lead Orders', compute='_compute_lead_count')
    lead_id = fields.Many2one('crm.lead', string='Lead')
    lead_ticket_flag = fields.Boolean(string='Lead Ticket Flag')
    
    # Champ calculé pour détecter si le ticket est annulé
    is_cancelled = fields.Boolean(
        compute='_compute_is_cancelled', 
        string='Est annulé', 
        store=True
    )
    
    # Champ calculé pour détecter si le ticket est clôturé
    is_closed = fields.Boolean(
        compute='_compute_is_closed',
        string='Est clôturé',
        store=True
    )
    
    @api.depends('stage_id')
    def _compute_is_cancelled(self):
        """Détermine si le ticket est dans le stage 'Cancelled'"""
        cancelled_stage = self.env.ref('helpdesk.stage_cancelled', raise_if_not_found=False)
        for ticket in self:
            ticket.is_cancelled = cancelled_stage and ticket.stage_id == cancelled_stage
    
    @api.depends('stage_id', 'stage_id.fold')
    def _compute_is_closed(self):
        """Détermine si le ticket est dans un stage fermé (fold=True)"""
        for ticket in self:
            ticket.is_closed = ticket.stage_id.fold if ticket.stage_id else False
    
    @api.depends('team_id', 'team_id.profile_id')
    def _compute_allowed_user_ids(self):
        """Calcule les utilisateurs autorisés selon le profil de l'équipe"""
        for ticket in self:
            if ticket.team_id and ticket.team_id.profile_id:
                # Chercher les utilisateurs ayant ce profil dans leur access_profile_line_ids
                # La relation est: res.users.access_profile_line_ids -> user.profiles
                users = self.env['res.users'].search([
                    ('access_profile_line_ids', 'in', ticket.team_id.profile_id.id)
                ])
                ticket.allowed_user_ids = users
            else:
                # Si pas d'équipe ou pas de profil, tous les utilisateurs sont autorisés
                ticket.allowed_user_ids = self.env['res.users'].search([])
    
    @api.onchange('team_id')
    def _onchange_team_id_filter_users(self):
        """Réinitialise user_id et multi_user_ids si les utilisateurs ne sont plus autorisés"""
        if self.team_id:
            # Recalculer les utilisateurs autorisés
            self._compute_allowed_user_ids()
            
            # Vérifier user_id
            if self.user_id and self.user_id not in self.allowed_user_ids:
                self.user_id = False
            
            # Vérifier multi_user_ids - retirer les utilisateurs non autorisés
            if self.multi_user_ids:
                # Filtrer pour ne garder que les utilisateurs autorisés
                authorized_multi_users = self.multi_user_ids.filtered(
                    lambda u: u in self.allowed_user_ids
                )
                # Si des utilisateurs ont été retirés, mettre à jour
                if len(authorized_multi_users) != len(self.multi_user_ids):
                    self.multi_user_ids = authorized_multi_users
    
    def _compute_lead_count(self):
        for order in self:
            lead_ids = self.env['crm.lead'].search([('ticket_id','=',self.id)])
            order.lead_count = len(lead_ids)
            
    def action_view_lead(self):
        action = self.env.ref('crm.crm_lead_all_leads').read()[0]
        lead_ids = self.env['crm.lead'].search([('ticket_id','=',self.id)])
        if len(lead_ids) > 1:
            action['domain'] = [('id', 'in', lead_ids.ids)]
        elif lead_ids:
            action['views'] = [(self.env.ref('crm.crm_lead_view_form').id, 'form')]
            action['res_id'] = lead_ids.id
        return action
    
    def create_lead(self):
        for data in self:
            return {
                'name': _('Leads'),
                'view_mode': 'form',
                'res_model': 'crm.lead',
                'view_id': self.env.ref('crm.crm_lead_view_form').id,
                'type': 'ir.actions.act_window',
                'context': {'default_name': self.name,
                            'default_partner_id': self.partner_id and self.partner_id.id or False,
                            'default_email_from': self.partner_id and self.partner_id.email or False,
                            'default_ticket_id': self.id,
                            },
                'target': 'new'
            }
    
#    dev_helpdesk_ticket_number_ent

    ticket_sequnce = fields.Char('Number',default="/")
    
    @api.model
    def create(self, vals):
        vals['ticket_sequnce'] = self.env['ir.sequence'].sudo().next_by_code('tickets.sequence') or 'New'
        ticket_ids = super(dev_helpdesk_ticket, self).create(vals)
        
        # Appliquer les SLAs (comme dans le code original)
        ticket_ids.sudo()._sla_apply()
        
        # Forcer le recalcul de due_date après l'application du SLA
        ticket_ids._compute_due_date()
        
        template_id = self.env.ref('dev_all_in_one_helpdesk_ent.mail_template_user_notification')
        if ticket_ids.company_id.notification_user_id:
            template_id.partner_to = ticket_ids.company_id.notification_user_id.partner_id.id
            template_id.send_mail(ticket_ids.id, True)
        return ticket_ids
    
    def write(self, vals):
        """Surcharge write pour recalculer due_date après les changements de SLA"""
        result = super(dev_helpdesk_ticket, self).write(vals)
        
        # Si des champs qui déclenchent le recalcul du SLA ont changé, recalculer due_date
        sla_triggers = self._sla_reset_trigger()
        if any(field_name in sla_triggers for field_name in vals.keys()):
            # Le parent a déjà appelé _sla_apply(), on invalide juste le cache et on recalcule
            self.invalidate_recordset(['due_date'])
            self._compute_due_date()
        
        return result
        
        
        
        
#    dev_helpdesk_solution_ent        

    solution_description = fields.Html(string='Solution')
    solution_document_ids = fields.One2many('ticket.solution.document','ticket_id',string='Solution Document')        
        
        

#    dev_helpdesk_report_ent
    
    def _get_report_base_filename(self):
        self.ensure_one()
        return '%s %s' % (_('Ticket'), self.ticket_sequnce)     
        
        
        
#    dev_helpdesk_sub_ticket_ent   
    parent_id = fields.Many2one('helpdesk.ticket', string='Parent')
    allow_subticket = fields.Boolean('Allow Subticket', compute='_check_allow_subticket')
    sub_ticket_count = fields.Integer('Sub Tickets', compute='_get_sub_ticket_count')
    
    def _get_sub_ticket_count(self):
        for ticket in self:
            ticket_ids = self.env['helpdesk.ticket'].search([('parent_id','=',self.id)])
            ticket.sub_ticket_count = len(ticket_ids)
            
    @api.depends('company_id')
    def _check_allow_subticket(self):
        for ticket in self:
            if ticket.company_id.helpdesk_subticket:
                ticket.allow_subticket = True
            else:
                ticket.allow_subticket = False
    
    
    def action_view_sub_tickets(self):
        action = self.env.ref('helpdesk.helpdesk_ticket_action_main_tree').read()[0]
        ticket_ids = self.env['helpdesk.ticket'].search([('parent_id','=',self.id)])
        if len(ticket_ids) > 1:
            action['domain'] = [('id', 'in', ticket_ids.ids)]
        elif ticket_ids:
            action['res_id'] = ticket_ids.id
            action['views'] = [(self.env.ref('helpdesk.helpdesk_ticket_view_form').id, 'form')]
        else:
            action['views'] = [(self.env.ref('helpdesk.helpdesk_ticket_view_form').id, 'form')]
            
        context={
            'default_parent_id':self.id,
            'default_name':self.name + ':',
            'default_partner_id':self.partner_id and self.partner_id.id or False,
            'default__partner_phone':self.partner_phone or '',
            'default_source_id':self.source_id and self.source_id.id or False,
            'default_company_id':self.company_id and self.company_id.id or False,
            'default_team_id':self.team_id and self.team_id.id or False,
            'default_user_id':self.user_id and self.user_id.id or False,
            'default_priority':self.priority,
            'default_tag_ids':[(6,0, self.tag_ids.ids)]
        }
        action['context'] = context
        return action  
        
        
#     dev_helpdesk_multi_user_ent   
        
    team_user_ids = fields.Many2many('res.users','team_res_user', string='team Users')
    multi_user_ids = fields.Many2many('res.users', string='Assign Multi Users')
    allow_multi_user = fields.Boolean('Allow Multi User', compute='_check_allow_multi_user')
    

    @api.depends('team_id', 'team_id.allow_multiple_assignment', 'company_id', 'company_id.allow_multi_user')
    def _check_allow_multi_user(self):
        """Vérifie si l'affectation multiple est autorisée (nécessite activation au niveau compagnie ET équipe)"""
        for ticket in self:
            ticket.allow_multi_user = False
            
            # Le champ est visible SEULEMENT si les DEUX conditions sont remplies:
            # 1. La compagnie autorise l'affectation multiple
            # 2. L'équipe autorise l'affectation multiple
            if ticket.company_id and ticket.company_id.allow_multi_user:
                if ticket.team_id and ticket.team_id.allow_multiple_assignment:
                    ticket.allow_multi_user = True        
                 
        

#    dev_helpdesk_due_reminder_ent

    due_date = fields.Datetime(
        'Date de clôture prévue',
        compute='_compute_due_date',
        store=True,
        readonly=True,
        help="Date d'échéance = date de création + temps du SLA (en heures)"
    )
    
    @api.depends('create_date', 'sla_ids', 'sla_ids.time')
    def _compute_due_date(self):
        """Calcule la date d'échéance: create_date + sla.time (en heures)"""
        from datetime import timedelta
        import logging
        _logger = logging.getLogger(__name__)
        
        _logger.info(f"=== _compute_due_date appelé pour {len(self)} ticket(s) ===")
        
        for ticket in self:
            _logger.info(f"Ticket {ticket.id}: Début calcul due_date")
            _logger.info(f"  - create_date: {ticket.create_date}")
            _logger.info(f"  - sla_ids: {ticket.sla_ids}")
            _logger.info(f"  - nombre de SLAs: {len(ticket.sla_ids)}")
            
            if not ticket.create_date:
                ticket.due_date = False
                _logger.warning(f"Ticket {ticket.id}: PAS de create_date!")
                continue
            
            # Récupérer le SLA le plus court (prioritaire)
            sla = ticket.sla_ids.sorted('time')[:1] if ticket.sla_ids else False
            
            if not sla:
                ticket.due_date = False
                _logger.warning(f"Ticket {ticket.id}: PAS de SLA associé (sla_ids vide)")
                continue
            
            _logger.info(f"  - SLA sélectionné: {sla.name} (time={sla.time}h)")
            
            # Calcul simple: date de création + temps du SLA en heures
            ticket.due_date = ticket.create_date + timedelta(hours=sla.time)
            _logger.info(f"Ticket {ticket.id}: ✓ due_date calculé = {ticket.due_date}")
    
    def get_due_date(self):
        if self.due_date:
            return self.due_date.strftime("%d-%m-%Y %H:%M:%S")
        else:
            return ''
            
            
#    dev_helpdesk_document_ent 
    attachment_count = fields.Integer(compute='_get_attachment_count',string='Attachment Count')
    
    def _get_attachment_count(self):
        for ticket in self:
            att_ids = self.env['ir.attachment'].search([('res_id','=',ticket.id),('res_model','=','helpdesk.ticket')])
            ticket.attachment_count = len(att_ids)
    
    def view_document(self):
        action = self.env.ref('base.action_attachment').read()[0]
        action['domain'] = [('res_id', '=', self.id),('res_model','=','helpdesk.ticket')]
        return action
        
        
#    dev_expense_helpdesk_ent    
    expense_count = fields.Integer(string='Expense', compute='_compute_expense_count')
    expense_id = fields.Many2one('hr.expense', string='Expense')
    expense_ticket_flag = fields.Boolean(string='Expense Ticket Flag')
    
    def _compute_expense_count(self):
        for order in self:
            expense_ids = self.env['hr.expense'].search([('ticket_id','=',self.id)])
            order.expense_count = len(expense_ids)

    def action_view_expense(self):
        action = self.env.ref('hr_expense.hr_expense_actions_my_all').read()[0]
        expense_ids = self.env['hr.expense'].search([('ticket_id','=',self.id)])
        if len(expense_ids) > 1:
            action['domain'] = [('id', 'in', expense_ids.ids)]
        elif expense_ids:
            action['views'] = [(self.env.ref('hr_expense.hr_expense_view_form').id, 'form')]
            action['res_id'] = expense_ids.id
        return action

    def create_expense(self):
        for data in self:
            employee_id = False
            if data.user_id:
                employee_id = self.env['hr.employee'].search([('user_id', '=', data.user_id.id)], limit=1)
            return {
                'name': _('Expense'),
                'view_mode': 'form',
                'res_model': 'hr.expense',
                'view_id': self.env.ref('hr_expense.hr_expense_view_form').id,
                'type': 'ir.actions.act_window',
                'context': {'default_name': self.name,
                            'default_employee_id': employee_id and employee_id.id or False,
                            'default_email_from': employee_id and employee_id.work_email or '',
                            'default_ticket_id': self.id,
                            },
                'target': 'new'
            }              



    

    @api.onchange('survey_template_id')
    def onchange_survey_template_id(self):
        if self.survey_template_id:
            data = []
            self.ticket_survey_ids = [(6, 0, [])]
            if self.survey_template_id and self.survey_template_id.survey_ids:
                for line in self.survey_template_id.survey_ids:
                    data.append((0, 0, {'survey_id': line.id}))
            if data:
                self.ticket_survey_ids = data
            else:
                self.ticket_survey_ids = [(6, 0, [])]

    survey_template_id = fields.Many2one('survey.template', string='Survey Template')
    ticket_survey_ids = fields.One2many('ticket.survey', 'ticket_id', string='Survey')
    
    
    
    
    
    
    main_request_count = fields.Integer(string='Maintenance Count', compute='_get_maintenance_count')


    def _get_maintenance_count(self):
        for ticket in self:
            request_ids = self.env['maintenance.request'].search([('ticket_id','=',ticket.id)])
            ticket.main_request_count = len(request_ids)

    def action_view_maintenance(self):
        action = self.env.ref('maintenance.hr_equipment_request_action').read()[0]
        main_request_ids = self.env['maintenance.request'].search([('ticket_id','=',self.id)])
        if len(main_request_ids) > 1:
            action['domain'] = [('id', 'in', main_request_ids.ids)]
        elif main_request_ids:
            action['views'] = [(self.env.ref('maintenance.hr_equipment_request_view_form').id, 'form')]
            action['res_id'] = main_request_ids.id
        note = ''
        if self.description:
            soup = BeautifulSoup(self.description)
            note = soup.get_text()
        emp_id = self.env['hr.employee'].search([('user_id','=',self.env.user.id)])
        context = {
            'default_name':self.ticket_sequnce or '',
            'default_employee_id':emp_id and emp_id.id or False,
            'default_user_id':self.env.user.id,
            'default_company_id':self.company_id.id or False,
            'default_ticket_id':self.id,
            'default_description':note,
        }
        action['context'] = context
        return action

    def create_ticket_maintenance(self):
        emp_id = self.env['hr.employee'].search([('user_id','=',self.env.user.id)])
        note = ''
        if self.description:
            soup = BeautifulSoup(self.description)
            note = soup.get_text()
        return {
            'name': _('Maintenance Request'),
            'view_mode': 'form',
            'res_model': 'maintenance.request',
            'view_id': self.env.ref('maintenance.hr_equipment_request_view_form').id,
            'type': 'ir.actions.act_window',
            'context': {
                        'default_name':self.ticket_sequnce or '',
                        'default_employee_id':emp_id and emp_id.id or False,
                        'default_user_id':self.env.user.id,
                        'default_company_id':self.company_id.id or False,
                        'default_ticket_id':self.id,
                        'default_description':note,
                        },
            'target': 'new'
        }










    

    def _get_task_count(self):
        for ticket in self:
            ticket_ids = self.env['project.task'].search([('ticket_id','=',ticket.id)])
            ticket.task_count = len(ticket_ids)

    def action_view_task(self):
        action = self.env.ref('project.action_view_all_task').read()[0]
        task_ids = self.env['project.task'].search([('ticket_id','=',self.id)])
        if len(task_ids) > 1:
            action['domain'] = [('id', 'in', task_ids.ids)]
        elif task_ids:
            action['views'] = [(self.env.ref('project.view_task_form2').id, 'form')]
            action['res_id'] = task_ids.id
        
        context = {
            'default_partner_id': self.partner_id and self.partner_id.id or False,
            'default_name':self.ticket_sequnce or '',
            'default_company_id':self.company_id.id or False,
            'default_description':self.description or '',
            'default_ticket_id':self.id,
        }
        action['context'] = context
        return action

    def create_ticket_task(self):
        for data in self:
            return {
                'name': _('Ticket Task'),
                'view_mode': 'form',
                'res_model': 'project.task',
                'view_id': self.env.ref('project.view_task_form2').id,
                'type': 'ir.actions.act_window',
                'context': {
                            'default_partner_id': self.partner_id and self.partner_id.id or False,
                            'default_name':self.ticket_sequnce or '',
                            'default_company_id':self.company_id.id or False,
                            'default_ticket_id':self.id,
                            'default_description':self.description or '',
                            },
                'target': 'new'
            }
    
    def action_cancel_ticket(self):
        """Annuler le ticket en le déplaçant vers le stage 'Cancelled'"""
        self.ensure_one()
        cancelled_stage = self.env.ref('helpdesk.stage_cancelled', raise_if_not_found=False)
        if not cancelled_stage:
            # Si le stage cancelled n'existe pas, chercher un stage avec fold=True et nom contenant 'cancel'
            cancelled_stage = self.env['helpdesk.stage'].search([
                ('team_ids', 'in', self.team_id.id),
                ('fold', '=', True),
                ('name', 'ilike', 'cancel')
            ], limit=1)

        if cancelled_stage:
            self.write({
                'stage_id': cancelled_stage.id,
                'close_date': fields.Datetime.now(),
            })
        else:
            from odoo.exceptions import UserError
            raise UserError(_("Aucun stage 'Annulé' n'a été trouvé pour cette équipe."))
    
    def action_save_ticket(self):
        """Enregistrer les modifications du ticket - équivalent au bouton Enregistrer d'Odoo"""
        # Cette méthode force la sauvegarde du formulaire
        # Elle retourne True pour fermer le formulaire si nécessaire
        return True
    
    def action_close_ticket(self):
        """Clôturer le ticket en le déplaçant vers un stage résolu"""
        for ticket in self:
            solved_stage = None
            
            # 1. Chercher le stage "Solved" par référence externe
            try:
                solved_stage = self.env.ref('helpdesk.stage_solved', raise_if_not_found=False)
            except:
                pass
            
            # 2. Si pas trouvé, chercher un stage avec is_solve = True pour cette équipe
            if not solved_stage:
                solved_stage = self.env['helpdesk.stage'].search([
                    ('is_solve', '=', True),
                    ('team_ids', 'in', ticket.team_id.id)
                ], limit=1)
            
            # 3. Si toujours pas trouvé, chercher n'importe quel stage résolu
            if not solved_stage:
                solved_stage = self.env['helpdesk.stage'].search([
                    ('is_solve', '=', True)
                ], limit=1)
            
            # 4. Chercher par nom (Solved, Done, Résolu, Closed, etc.)
            if not solved_stage:
                solved_stage = self.env['helpdesk.stage'].search([
                    '|', '|', '|',
                    ('name', 'ilike', 'solved'),
                    ('name', 'ilike', 'done'),
                    ('name', 'ilike', 'résolu'),
                    ('name', 'ilike', 'closed')
                ], limit=1)
            
            # 5. En dernier recours, prendre le dernier stage de l'équipe
            if not solved_stage:
                solved_stage = self.env['helpdesk.stage'].search([
                    ('team_ids', 'in', ticket.team_id.id)
                ], order='sequence desc', limit=1)
            
            if solved_stage:
                ticket.write({'stage_id': solved_stage.id})
            else:
                raise ValidationError(_("Aucun stage n'a été trouvé pour clôturer ce ticket."))
        
        return True

            
            
            
            
class helpdesk_stage(models.Model):
    _inherit = 'helpdesk.stage'
    
    is_solve = fields.Boolean(string='Is Solve')            
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:




