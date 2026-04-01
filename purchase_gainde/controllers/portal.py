# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError, MissingError
from odoo.addons.bf_portal_purchase_request.controllers.portal import PurchaseRequestPortal


class PurchaseRequestPortalGainde(PurchaseRequestPortal):
    
    def _pr_get_mandatory_fields(self):
        """Remove nature and threshold from mandatory fields"""
        # Get the original mandatory fields from the parent class
        mandatory_fields = super()._pr_get_mandatory_fields().copy()
        # Remove 'picking_type_id' from the mandatory fields list
        if 'picking_type_id' in mandatory_fields:
            
            mandatory_fields.remove('picking_type_id')
        if 'company_id' in mandatory_fields:
            mandatory_fields.remove('company_id')
        if  'date_start' in mandatory_fields:
               mandatory_fields.remove('date_start')

            
        return mandatory_fields

    def _pr_get_optional_fields(self):
        """Remove picking_type_id from optional fields"""
        optional_fields = super()._pr_get_optional_fields().copy()
        # Remove picking_type_id from optional fields as well
        if 'picking_type_id' in optional_fields:
            optional_fields.remove('picking_type_id')
        if 'company_id' in optional_fields: 
            optional_fields.remove('company_id')
        if 'date_start' in optional_fields:
            optional_fields.remove('date_start')    
        return optional_fields

    @http.route([
        '/my/purchase_requests/<int:purchase_request_id>',
        '/my/purchase_requests/<int:purchase_request_id>/<access_token>'], 
        type='http', auth="user", website=True)
    def portal_my_purchase_request_detail(self, purchase_request_id, report_type=None, access_token=None, download=False, **post):
        """Override to remove nature and threshold references"""
        try:
            purchase_request_sudo = self._document_check_access('purchase.request', purchase_request_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        # Report
        if report_type in ('html', 'pdf', 'text'):
            return self._show_report(
                model=purchase_request_sudo,
                report_type=report_type,
                report_ref='purchase_request.action_report_purchase_requests',
                download=download,
            )

        values = self._prepare_portal_layout_values()
        values.update({
            'error': {},
            'error_message': [],
        })

        if post and request.httprequest.method == 'POST':
            error, error_message = self._pr_details_form_validate(post)
            values.update({'error': error, 'error_message': error_message})
            values.update(post)
            
            if not error:
                vals = {key: post[key] for key in self._pr_get_mandatory_fields()}
                vals.update({key: post[key] for key in self._pr_get_optional_fields() if key in post})
                
                # Convert integer fields
                for field in set(['requested_by', 'assigned_to', 'picking_type_id', 'company_id']) & set(vals.keys()):
                    try:
                        vals[field] = int(vals[field])
                    except:
                        vals[field] = False
                
                if vals.get("line_ids"):
                    import json
                    line_ids = json.loads(vals.get("line_ids"))
                    vals.update({'line_ids': line_ids})
                else:
                    vals.pop('line_ids', '')
                
                # Update the purchase request
                purchase_request_sudo.write(vals)
                
                # Add message to chatter
                body = _('Your purchase request has been edited from the portal.')
                purchase_request_sudo.with_context(mail_create_nosubscribe=True).message_post(
                    body=body, message_type='comment', subtype_xmlid='mail.mt_note', 
                    author_id=request.env.user.partner_id.id)
                
                return request.redirect('/my/purchase_requests/%s' % (purchase_request_id))

        # Remove nature and threshold data from context
        values.update({
            'users': request.env['res.users'].sudo().search([]),
            'uoms': request.env['uom.uom'].sudo().search([]),
            'companies': request.env.user.company_ids,
            # 'date_start': purchase_request_sudo.date_start,
            'picking_types': request.env['stock.picking.type'].sudo().search([]),
            'assigned_users': request.env['res.users'].sudo().search([
                ('groups_id', 'in', request.env.ref("purchase_request.group_purchase_request_manager").id)]),
        })

        values.update(self._purchase_request_get_page_view_values(purchase_request_sudo, access_token, **post))
        
        response = request.render("bf_portal_purchase_request.bf_portal_purchase_request_page", values)
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
        return response
    @http.route([
        '/my/purchase_requests/approve/<int:purchase_request_id>',
        '/my/purchase_requests/approve/<int:purchase_request_id>/<access_token>'], type='http', auth="user", website=True)
    def to_approve(self, purchase_request_id=None, access_token=None, **kw):
        # Ref.: helpdesk/controllers/portal.py (ticket_close)
        try:
            purchase_request_sudo = self._document_check_access('purchase.request', purchase_request_id, access_token)
        except (AccessError, MissingError):

            return request.redirect('/my')

        if purchase_request_sudo.state == 'draft':
            if not purchase_request_sudo.requested_by.employee_id.coach_id:
                return request.redirect('/my')

            # S'il n'y a pas de lignes, rester sur la fiche et
            # afficher un message d'erreur dans le portail plutôt
            # que de revenir silencieusement à la liste.
            if not purchase_request_sudo.line_ids:
                return request.redirect('/my/purchase_requests/%s/%s?no_lines=1' % (purchase_request_id, access_token or ''))

            purchase_request_sudo.action_n2_line_approved()
            
                
            #purchase_request_sudo.button_to_approve()
            # Su solicitud de compra a sido enviada desde el portal para ser aprobada.
            body = _('Votre demande d\'achat a été envoyée depuis le portail pour approbation.')
            purchase_request_sudo.with_context(mail_create_nosubscribe=True).message_post(
                body=body, message_type='comment', subtype_xmlid='mail.mt_note', author_id=request.env.user.partner_id.id)
            return request.redirect('/my/purchase_requests/%s/%s?request_approve=1' % (purchase_request_id, access_token or ''))
        else:
            return request.redirect('/my')

    @http.route(['/my/purchase_requests/new'], type='http', auth="user", website=True)
    def portal_my_purchase_request_new(self, **post):
        """Override to remove nature and threshold references"""
        from odoo import fields, _
        import json
        
        purchase_request_sudo = request.env['purchase.request'].sudo()

        values = self._prepare_portal_layout_values()
        values.update({
            'error': {},
            'error_message': [],
            'page_name': 'purchase_request',
        })

        if post and request.httprequest.method == 'POST':
            error, error_message = self._pr_details_form_validate(post)
            values.update({'error': error, 'error_message': error_message})
            values.update(post)
            
            if not error:
                vals = {key: post[key] for key in self._pr_get_mandatory_fields()}
                vals.update({key: post[key] for key in self._pr_get_optional_fields() if key in post})
                
                # Convert integer fields
                for field in set(['requested_by', 'assigned_to', 'picking_type_id', 'company_id']) & set(vals.keys()):
                    try:
                        vals[field] = int(vals[field])
                    except:
                        vals[field] = False
                
                if vals.get("line_ids"):
                    line_ids = json.loads(vals.get("line_ids"))
                    vals.update({'line_ids': line_ids})
                else:
                    vals.pop('line_ids', '')
                
                # Create the purchase request
                purchase_request_id = purchase_request_sudo.create(vals)
                
                # Add message to chatter
                body = _('Your purchase request has been created from the portal.')
                purchase_request_id.with_context(mail_create_nosubscribe=True).message_post(
                    body=body, message_type='comment', subtype_xmlid='mail.mt_note', 
                    author_id=request.env.user.partner_id.id)
                
                return request.redirect('/my/purchase_requests/%s?request_create=1' % (purchase_request_id.id))

        # Remove nature and threshold data from context
        values.update({
            'users': request.env['res.users'].sudo().search([]),
            'uoms': request.env['uom.uom'].sudo().search([]),
            'companies': request.env.user.company_ids,
            'picking_types': request.env['stock.picking.type'].sudo().search([]),
            'default_requested_by': request.env.user,
            'default_date_start': fields.Date.context_today(request.env.user),
            'assigned_users': request.env['res.users'].sudo().search([
                ('groups_id', 'in', request.env.ref("purchase_request.group_purchase_request_manager").id)]),
        })

        response = request.render("bf_portal_purchase_request.portal_new_purchase_request_page", values)
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
        return response