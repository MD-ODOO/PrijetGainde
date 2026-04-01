from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError, AccessError
from odoo.tools.safe_eval import safe_eval

from . import selection


class ApprovalRouteDocument(models.AbstractModel):
    _name = 'approval.route.document'
    _description = 'Document Approval'

    _sub_records_o2m_fields = None

    approval_route_id = fields.Many2one(
        string='Approval Route',
        comodel_name='approval.route',
        domain=lambda self: [('model', '=', self._name)]
    )
    approval_route_stage_ids = fields.One2many(
        string='Approval Stages',
        comodel_name='approval.route.document.stage',
        inverse_name='res_id',
        domain=lambda self: [('res_model', '=', self._name)],
        readonly=True,
    )
    current_approval_stage_id = fields.Many2one(
        string='Current Approval Stage',
        comodel_name='approval.route.document.stage',
        compute='_compute_approval_stage',
        store=True,
        compute_sudo=True,
    )
    next_approval_stage_id = fields.Many2one(
        string='Next Approval Stage',
        comodel_name='approval.route.document.stage',
        compute='_compute_approval_stage',
        store=True,
        compute_sudo=True,
    )
    is_under_approval = fields.Boolean(
        string='Is Under Approval',
        compute='_compute_approval_stage',
        store=True,
        compute_sudo=True,
        help='True if document is waiting approval'
    )
    is_approval_received = fields.Boolean(
        string='Is Approval Received',
        compute='_compute_approval_stage',
        store=True,
        compute_sudo=True,
        help='True if document received approval from at least one approver'
    )
    is_fully_approved = fields.Boolean(
        string='Is Fully Approved',
        compute='_compute_approval_stage',
        store=True,
        compute_sudo=True,
        help='True if document received approval from all approvers'
    )
    is_current_approver = fields.Boolean(
        string='Is Current Approver',
        compute='_compute_is_current_approver',
        search='_search_is_current_approver',
    )

    @api.depends('approval_route_stage_ids', 'approval_route_stage_ids.state')
    def _compute_approval_stage(self):
        for record in self:
            stages = record.approval_route_stage_ids
            next_stages = stages.filtered(lambda s: s.state == selection.APPROVAL_STATE_TO_APPROVE)
            record.next_approval_stage_id = next_stages[0] if next_stages else None

            current_stage = stages.filtered(lambda s: s.state == selection.APPROVAL_STATE_PENDING)
            record.current_approval_stage_id = current_stage[0] if current_stage else None

            approved_stages = stages.filtered(lambda s: s.state == selection.APPROVAL_STATE_APPROVED)
            record.is_approval_received = len(approved_stages)

            record.is_under_approval = bool(next_stages or current_stage)
            record.is_fully_approved = record._is_fully_approved()

    def _is_fully_approved(self):
        self.ensure_one()
        return set(self.approval_route_stage_ids.mapped('state')) == {selection.APPROVAL_STATE_APPROVED}

    @api.depends('current_approval_stage_id')
    def _compute_is_current_approver(self):
        for record in self:
            record.is_current_approver = (
                    record.current_approval_stage_id and
                    (self.env.user in record.current_approval_stage_id.user_ids or self.env.is_superuser())
            )

    def _search_is_current_approver(self, operator, value):
        if operator in ('=', 'in'):
            return [('current_approval_stage_id.user_ids', 'in', value)]
        elif operator in ('!=', 'not in'):
            return [('current_approval_stage_id.user_ids', 'not in', value)]

    @api.model
    def check_field_access_rights(self, operation, fields):
        if operation == 'write':
            self._check_locked_fields(fields)
        return super(ApprovalRouteDocument, self).check_field_access_rights(operation, fields)

    def _write(self, vals):
        self._check_locked_fields(vals.keys())
        return super(ApprovalRouteDocument, self)._write(vals)

    def _check_locked_fields(self, fields):
        for record in self:
            if not record.is_under_approval and not record.is_approval_received:
                # Skip if the document has not been approved by any approver yet
                continue
            approval_route = record.approval_route_id
            if not approval_route.lock_fields:
                # Skip if the option is disabled
                continue
            locked_fields = set(record.approval_route_id.sudo().locked_fields.mapped('name'))
            if set(fields) & locked_fields:
                reason = ''
                if record.is_approval_received:
                    reason = _(', as approval has been received from one or more approvers.')
                elif record.is_under_approval:
                    reason = _(', as it is currently under approval.')
                msg = [
                    _('The document locking option is enabled in the approval workflow settings.'),
                    _('This document cannot be modified %s') % reason
                ]
                raise AccessError('\n'.join(msg))

    def _action_approve(self):
        self.action_make_decision(selection.APPROVAL_STATE_APPROVED)

    def _action_reject(self):
        self.action_make_decision(selection.APPROVAL_STATE_REJECTED)
    def action_make_apply_no_sms_decision(self, decision):
        for record in self:
            approval_stage = record.current_approval_stage_id
            if not record.current_approval_stage_id:
                raise UserError(_('This %s is not under approval!') % self._description)

            approvers = approval_stage.user_ids
            names = approvers.mapped('name')
            if self.env.user not in approvers and not self.env.is_superuser():
                raise AccessError(_('This %s must be approved by %s') % (self._description, ' or '.join(names)))

            decisions = approval_stage.decisions or {}
            decisions.update({str(self.env.user.id): decision})
            approval_stage.decisions = decisions

            record.message_post(body=_('%s %s by %s') % (self._description, decision, self.env.user.name))

            if decision == selection.APPROVAL_STATE_APPROVED:
                # If user approved document, state is changed according to approval type (one or all)
                if approval_stage.approval_type == selection.APPROVAL_TYPE_ONE:
                    approval_stage.state = decision
                elif approval_stage.approval_type == selection.APPROVAL_TYPE_ALL:
                    decisions_set = set()
                    for approver in approvers:
                        decisions_set.add(decisions.get(str(approver.id), selection.APPROVAL_STATE_PENDING))
                    # If all approvers approved document, state is changed as "approved", else as "pending"
                    approval_stage.state = decision if decisions_set == {decision} else \
                        selection.APPROVAL_STATE_PENDING
            elif decision == selection.APPROVAL_STATE_REJECTED:
                # If user rejected document, state is changed as "rejected"
                approval_stage.state = decision

            if record._is_fully_approved():
                record.message_post(body=_('%s was fully approved') % self._description)
            elif approval_stage.state == selection.APPROVAL_STATE_APPROVED and record.next_approval_stage_id:
    
                record._action_send_to_nomail_approve()

    def action_make_apply_rnd_decision(self, decision):
        for record in self:
            approval_stage = record.current_approval_stage_id
            if not record.current_approval_stage_id:
                raise UserError(_('This %s is not under approval!') % self._description)

            approvers = approval_stage.user_ids
            names = approvers.mapped('name')
            if self.env.user not in approvers and not self.env.is_superuser():
                raise AccessError(_('This %s must be approved by %s') % (self._description, ' or '.join(names)))

            decisions = approval_stage.decisions or {}
            decisions.update({str(self.env.user.id): decision})
            approval_stage.decisions = decisions

            record.message_post(body=_('%s %s by %s') % (self._description, decision, self.env.user.name))

            if decision == selection.APPROVAL_STATE_APPROVED:
                # If user approved document, state is changed according to approval type (one or all)
                if approval_stage.approval_type == selection.APPROVAL_TYPE_ONE:
                    approval_stage.state = decision
                elif approval_stage.approval_type == selection.APPROVAL_TYPE_ALL:
                    decisions_set = set()
                    for approver in approvers:
                        decisions_set.add(decisions.get(str(approver.id), selection.APPROVAL_STATE_PENDING))
                    # If all approvers approved document, state is changed as "approved", else as "pending"
                    approval_stage.state = decision if decisions_set == {decision} else \
                        selection.APPROVAL_STATE_PENDING
            elif decision == selection.APPROVAL_STATE_REJECTED:
                # If user rejected document, state is changed as "rejected"
                approval_stage.state = decision

            if record._is_fully_approved():
                record.message_post(body=_('%s was fully approved') % self._description)
            elif approval_stage.state == selection.APPROVAL_STATE_APPROVED and record.next_approval_stage_id:
               
                record._action_send_to_rnd_approve()

    def action_make_apply_rnd_decision(self, decision):
     for record in self:
        stage = record.current_approval_stage_id
        if not stage:
            raise UserError(_('This %s is not under approval!') % self._description)

        approvers = stage.user_ids
        if self.env.user not in approvers and not self.env.is_superuser():
            raise AccessError(_('You are not allowed to approve this document.'))

        decisions = dict(stage.decisions or {})
        decisions[str(self.env.user.id)] = decision
        stage.sudo().write({'decisions': decisions})

        record.message_post(
            body=_('%s %s by %s') % (self._description, decision, self.env.user.name)
        )

        if decision == selection.APPROVAL_STATE_APPROVED:
            if stage.approval_type == selection.APPROVAL_TYPE_ONE:
                stage.sudo().write({'state': decision})
            elif stage.approval_type == selection.APPROVAL_TYPE_ALL:
                decisions_set = {
                    decisions.get(str(u.id), selection.APPROVAL_STATE_PENDING)
                    for u in approvers
                }
                stage.sudo().write({
                    'state': decision if decisions_set == {decision}
                    else selection.APPROVAL_STATE_PENDING
                })
        elif decision == selection.APPROVAL_STATE_REJECTED:
            stage.sudo().write({'state': decision})

        if record._is_fully_approved():
            record.message_post(body=_('%s was fully approved') % self._description)
        elif stage.state == selection.APPROVAL_STATE_APPROVED and record.next_approval_stage_id:
            record._action_send_to_rnd_approve()
    
    def _action_send_to_rnd_approve(self):
     for record in self:
        message_body = _(
            'Dear colleagues,<br/>'
            'You have been requested to approve the %s "%s"'
        ) % (self._description, record.display_name)

        partner_ids = set()
        user_ids = set()

        for line in getattr(record, 'line_ids', []):
            product = line.product_id
            categ = product.categ_id if product else False
            profile = getattr(categ, 'user_profile_id', False)

            if profile and hasattr(profile, 'access_user_ids'):
                for user in profile.access_user_ids:
                    if user.partner_id:
                        user_ids.add(user.id)
                        partner_ids.add(user.partner_id.id)

        # Fallback : approvers de l’étape suivante
        if not partner_ids and record.next_approval_stage_id:
            for user in record.next_approval_stage_id.user_ids:
                if user.partner_id:
                    user_ids.add(user.id)
                    partner_ids.add(user.partner_id.id)

        if partner_ids:
            record.message_post(body=message_body, partner_ids=list(partner_ids))
        else:
            record.message_post(body=message_body)

        if record.next_approval_stage_id:
            record.current_approval_stage_id.sudo().write({
                'user_ids': [(Command.set(list(user_ids)))]
            })
            record.next_approval_stage_id.sudo().write({
                'state': selection.APPROVAL_STATE_PENDING
            })



    def _action_send_to_rnd_approve(self):
        for record in self:
            # use sudo as purchase user cannot update purchase.order.approver
            message_body = _('''
            Dear colleagues,
            You have been requested to approve the %s "%s"
            ''') % (self._description, record.display_name)

            partner_ids_set = set()
            user_ids_set = set()
            for line in record.line_ids:
                product = line.product_id
                categ = product.categ_id if product else False
                profile = getattr(categ, 'user_profile_id', False)
                if profile:
                    #raise UserError(_('Profile trouvé: %s') % profile.name)
                    for user in getattr(profile, 'access_user_ids', self.env['res.users']):
                        if user.partner_id:
                            user_ids_set.add(user.id)
                            partner_ids_set.add(user.partner_id.id)

            # Fallback: si aucun partenaire trouvé via rnd_profile, notifier les approbateurs de l'étape suivante
            if not partner_ids_set and record.next_approval_stage_id:
                partner_ids_set.update(record.next_approval_stage_id.user_ids.mapped('partner_id').ids)

            if partner_ids_set:
                #raise UserError(partner_ids_set)
                record.message_post(body=message_body, partner_ids=list(partner_ids_set))
           
            else:
                # Pas de partenaires à notifier, au moins logguer l’évènement
                record.message_post(body=message_body)
                #user_ids=record.next_approval_stage_id.user_ids.mapped('id')
            record.current_approval_stage_id.sudo().write({'user_ids': [(6, 0, list(user_ids_set))]})

            if record.next_approval_stage_id:

                record.next_approval_stage_id.sudo().state = 'pending'
                #record.current_approval_stage_id.sudo().write({'user_ids': [(6, 0, list(user_ids_set))]})
                #raise AccessError(record.current_approval_stage_id.user_ids.ids)

    def _action_send_to_nomail_approve(self):
        for record in self:
            # use sudo as purchase user cannot update purchase.order.approver
            message_body = _('''
            Dear colleagues,
            You have been requested to approve the %s "%s"
            ''') % (self._description, record.display_name)
            #partners = record.next_approval_stage_id.user_ids.mapped('partner_id')
            #user_ids=record.next_approval_stage_id.user_ids.mapped('id')
            #record.message_post(body=message_body, partner_ids=partners.ids)
            record.next_approval_stage_id.sudo().state = 'pending'
             
    def action_make_decision(self, decision):
        for record in self:
            
            approval_stage = record.current_approval_stage_id
            if not record.current_approval_stage_id:
                raise UserError(_('This %s is not under approval!') % self._description)

            approvers = approval_stage.user_ids
            names = approvers.mapped('name')
            if self.env.user not in approvers and not self.env.is_superuser():
                raise AccessError(_('This %s must be approved by %s') % (self._description, ' or '.join(names)))

            decisions = approval_stage.decisions or {}
            decisions.update({str(self.env.user.id): decision})
            approval_stage.decisions = decisions

            record.message_post(body=_('%s %s by %s') % (self._description, decision, self.env.user.name))

            if decision == selection.APPROVAL_STATE_APPROVED:
                # If user approved document, state is changed according to approval type (one or all)
                if approval_stage.approval_type == selection.APPROVAL_TYPE_ONE:
                    approval_stage.state = decision
                elif approval_stage.approval_type == selection.APPROVAL_TYPE_ALL:
                    decisions_set = set()
                    for approver in approvers:
                        decisions_set.add(decisions.get(str(approver.id), selection.APPROVAL_STATE_PENDING))
                    # If all approvers approved document, state is changed as "approved", else as "pending"
                    approval_stage.state = decision if decisions_set == {decision} else \
                        selection.APPROVAL_STATE_PENDING
            elif decision == selection.APPROVAL_STATE_REJECTED:
                # If user rejected document, state is changed as "rejected"
                approval_stage.state = decision

            if record._is_fully_approved():
                record.message_post(body=_('%s was fully approved') % self._description)
            elif approval_stage.state == selection.APPROVAL_STATE_APPROVED and record.next_approval_stage_id:
                
                record._action_send_to_approve()

    def _action_send_to_approve(self):
        for record in self:
            # use sudo as purchase user cannot update purchase.order.approver
            message_body = _('''
            Dear colleagues,
            You have been requested to approve the %s "%s"
            ''') % (self._description, record.display_name)
            partners = record.next_approval_stage_id.user_ids.mapped('partner_id')
            user_ids=record.next_approval_stage_id.user_ids.mapped('id')
            record.message_post(body=message_body, partner_ids=partners.ids)
            record.next_approval_stage_id.sudo().state = 'pending'
    
    def _get_globals_dict(self):
        return {
            'self': self,
            'env': self.env,
            'user': self.env.user,
        }

    def compute_custom_condition(self, approval_stage):
        self.ensure_one()
        globals_dict = self._get_globals_dict()
        if not approval_stage.condition_code:
            return True
        try:
            safe_eval(approval_stage.condition_code, globals_dict, mode='exec', nocopy=True)
            return bool(globals_dict['result'])
        except Exception as e:
            raise UserError(_('Wrong condition code defined for %s. Error: %s') % (approval_stage.display_name, e))

    def compute_amount_condition(self, approval_stage):
        self.ensure_one()
        if (not approval_stage.condition_amount_field_id or
                not approval_stage.condition_amount_operator or
                not approval_stage.condition_amount_currency_id):
            return True

        monetary_field = self._fields[approval_stage.condition_amount_field_id.name]
        monetary_currency_field = monetary_field.get_currency_field(self)

        # Convert amount from document to approval stage currency
        amount = self[monetary_currency_field]._convert(
            getattr(self, approval_stage.condition_amount_field_id.name),  # amount from document
            approval_stage.condition_amount_currency_id,  # approval stage currency
            approval_stage.approval_route_id.company_id,
            fields.Date.context_today(self)
        )
        if approval_stage.condition_amount_operator == selection.AMOUNT_TERM_LE_OPERATOR:
            return amount <= approval_stage.condition_amount
        if approval_stage.condition_amount_operator == selection.AMOUNT_TERM_GE_OPERATOR:
            return amount >= approval_stage.condition_amount

        return True

    def compute_m2m_condition(self, approval_stage, relation_type):
        m2m_field = approval_stage[f'condition_{relation_type}_field_id']
        m2m_operator = approval_stage[f'condition_{relation_type}_operator']
        m2m_condition_records = approval_stage[f'condition_{relation_type}_ids']
        if not m2m_field or not m2m_operator or not m2m_condition_records:
            return True

        m2m_records = self[m2m_field.name]

        if m2m_operator == selection.M2M_POSITIVE_TERM_OPERATOR:
            return bool(m2m_records & m2m_condition_records)
        if m2m_operator == selection.M2M_NEGATIVE_TERM_OPERATOR:
            return not bool(m2m_records & m2m_condition_records)

    def _clear_approval_stages(self):
        for record in self:
            if record.approval_route_stage_ids:
                # reset approval stages
                record.approval_route_stage_ids.unlink()

    def generate_approval_route(self):
        """
        Generate approval route for order
        :return:
        """
        for record in self:
            if not record.approval_route_id:
                continue
            record._clear_approval_stages()

            for approval_stage in record.approval_route_id.sudo().stage_ids:
                if not approval_stage.use_custom_conditions:
                    # If custom conditions are not set, just add approval stage for the document
                    record.add_document_stage(approval_stage)
                    continue
                # Else, compute if the approval stage is applicable for that document
                amount_condition = record.compute_amount_condition(approval_stage)
                if not amount_condition:
                    continue
                m2m_condition = True
                for m2m_relation_type in approval_stage._m2m_relation_types:
                    m2m_condition = record.compute_m2m_condition(approval_stage, m2m_relation_type)
                    if not m2m_condition:
                        break
                if not m2m_condition:
                    continue

                custom_condition = record.compute_custom_condition(approval_stage)
                if not custom_condition:
                    continue
                # If all custom conditions are met, add approval stage for the document
                record.add_document_stage(approval_stage)

    def add_document_stage(self, approval_stage):
        """
        Add approval stage for the document
        :param object approval_stage: approval.route.stage
        :return:
        """
        self.ensure_one()
        self.env['approval.route.document.stage'].create({
            'res_model': self._name,
            'res_id': self.id,
            'sequence': approval_stage.sequence,
            'name': approval_stage.name,
            'user_ids': [Command.set(approval_stage.computed_user_ids.ids)],
            'approval_type': approval_stage.approval_type,
            'state': selection.APPROVAL_STATE_TO_APPROVE,
        })


class ApprovalRouteDocumentStage(models.Model):
    _name = 'approval.route.document.stage'
    _description = 'Document Approval Stage'
    _order = 'sequence, id'

    res_model = fields.Char(
        string='Related Document Model Name',
        required=True,
        index=True,
    )
    res_id = fields.Many2oneReference(
        string='Related Document ID',
        required=True,
        index=True,
        model_field='res_model',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=1,
    )
    name = fields.Char(
        string='Stage',
        required=True,
    )
    user_ids = fields.Many2many(
        string='Approvers',
        comodel_name='res.users',
        relation='approval_route_document_stage_users',
        column1='document_stage_id',
        column2='user_id',
    )
    approval_type = fields.Selection(
        string='Approval Type',
        selection=selection.APPROVAL_TYPES,
        default=selection.APPROVAL_TYPE_ONE,
    )
    decisions = fields.Json(
        string='Decisions (Serialized)',
    )
    decisions_summary = fields.Text(
        string='Decisions (Summary)',
        compute='_compute_decisions_summary',
    )
    state = fields.Selection(
        string='Status',
        selection=selection.APPROVAL_STATES,
        readonly=True,
        required=True,
        default=selection.APPROVAL_STATE_TO_APPROVE,
    )

    @api.depends('decisions')
    def _compute_decisions_summary(self):
        for stage in self:
            summary = ''
            if isinstance(stage.decisions, dict):
                # If there is at least one decision generate user-friendly summary
                for user_id, decision in stage.decisions.items():
                    user = stage.user_ids.filtered_domain([('id', '=', int(user_id))])
                    summary += f'* {user.name}: {decision} \n'
            stage.decisions_summary = summary
