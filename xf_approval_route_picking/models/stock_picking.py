# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.addons.xf_approval_route_base.models import selection
from odoo.exceptions import ValidationError


class Picking(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking', 'approval.route.document']

    state = fields.Selection(
        selection_add=[
            ('to approve', 'To Approve'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('done',),
        ],
        ondelete={
            'to approve': 'set draft',
            'approved': 'set draft',
            'rejected': 'set draft',
        }
    )

    use_approval_route = fields.Selection(
        string="Use Approval Route",
        selection=selection.USE_APPROVAL_ROUTE,
        compute='_compute_use_approval_route',
    )
    approval_route_id = fields.Many2one(
        readonly=True,
    )

    def button_draft(self):
        for picking in self:
            if picking.state == 'rejected':
                picking.state = 'draft'

    @api.depends('company_id')
    def _compute_use_approval_route(self):
        for picking in self:
            picking.use_approval_route = picking.company_id.use_approval_route_picking

    def _track_subtype(self, init_values):
        self.ensure_one()
        if init_values.get('state') == 'to approve':
            if self.state == 'done':
                return self.env.ref('xf_approval_route_picking.mt_picking_approved_and_validated')
            if self.state == 'rejected':
                return self.env.ref('xf_approval_route_picking.mt_picking_rejected')
        return super(Picking, self)._track_subtype(init_values)

    def button_validate(self):
        for picking in self:
            if picking.use_approval_route != 'no' and picking.approval_route_id:
                if picking.state == 'rejected':
                    raise ValidationError(_('You cannot validate rejected transfer! Please reset it to draft to proceed.'))
                elif picking.state == 'to approve':
                    raise ValidationError(_('This transfer is waiting for approval! You cannot validate it.'))
                else:
                    # Generate approval workflow and send picking to approve
                    picking.generate_approval_route()
                    if picking.next_approval_stage_id:
                        # If approval route was generated and there is next approver,
                        # mark the picking as 'to approve'
                        picking.write({'state': 'to approve'})
                        # And send request to approve
                        picking._action_send_to_approve()
                    else:
                        # If there are no approvers, do default behaviour
                        super(Picking, picking).button_validate()
            else:
                # Do default behaviour, if approval route is not set
                # or approval functionality is disabled
                super(Picking, picking).button_validate()

    def button_approve(self):
        for picking in self:
            if picking.current_approval_stage_id:
                picking._action_approve()
                if picking._is_fully_approved():
                    # If fully approved, do default behaviour
                    super(Picking, picking).button_validate()
            else:
                # Do default behaviour if approval route is not set
                super(Picking, picking).button_validate()

    def button_reject(self):
        for picking in self:
            if picking.current_approval_stage_id:
                picking._action_reject()
                picking.write({'state': 'rejected'})
