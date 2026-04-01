# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import OrderedDict
from odoo import fields, http, _, SUPERUSER_ID
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
# from odoo.addons.portal.controllers.mail import _message_post_helper
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager, get_records_pager
from odoo.osv import expression
import werkzeug
from datetime import datetime, date
from odoo.tools import groupby as groupbyelem
from operator import itemgetter
from datetime import timedelta
from dateutil.relativedelta import relativedelta
import base64
from odoo.osv.expression import OR

class CustomerPortal(CustomerPortal):

    @http.route([
        "/helpdesk/ticket/<int:ticket_id>",
        "/helpdesk/ticket/<int:ticket_id>/<access_token>",
        '/my/ticket/<int:ticket_id>',
        '/my/ticket/<int:ticket_id>/<access_token>'
    ], type='http', auth="public", website=True)
    def tickets_followup(self, ticket_id=None, access_token=None,report_type=None,download=False, **kw):
        try:
            ticket_sudo = self._document_check_access('helpdesk.ticket', ticket_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
		
        if report_type in ('html', 'pdf', 'text'):
        	return self._show_report(model=ticket_sudo, report_type=report_type, report_ref='dev_all_in_one_helpdesk_ent.ticket_menu_template', download=download)
        values = self._ticket_get_page_view_values(ticket_sudo, access_token, **kw)
#        values.update({
#        'ticket': ticket_sudo,   # <-- Add ticket_sudo to values here
#        })
        return request.render("helpdesk.tickets_followup", values)




    @http.route(['/dev_helpdesk_ticket_track'], type='json', methods=['POST'], website=True, auth="public")
    def dev_track_delivery_order(self, do_no, **kw):
        ticket_id = request.env['helpdesk.ticket'].sudo().search([('ticket_sequnce','=',do_no)],limit=1)
        number = name = status = False
        if ticket_id:
            status =  ticket_id.stage_id.name
            number = ticket_id.ticket_sequnce
            name = ticket_id.name
            
            address = ''
            partner = ticket_id.partner_id
            if partner:
                if partner.street:
                    if address:
                        address = address +', ' +partner.street
                    else:
                        address = partner.street
                
                if partner.street2:
                    if address:
                        address = address+', ' + partner.street2
                    else:
                        address = partner.street2
                
                if partner.city:
                    if address:
                        address = address +', ' + partner.city
                    else:
                        address = partner.city + '\n'
            city = partner.city
            if partner.zip:
                if city:
                    city = city+ '  ' + partner.zip
                else:
                    city = partner.zip
            if partner.country_id:
                if city:
                    city = city +' , '+ partner.country_id.name
                else:
                    city = partner.country_id.name
            
            res = {
                'customer':partner.name or '',
                'street':partner.street or '',
                'street2':partner.street2 or '',
                'city':city or '',
                'status':status,
                'address':address or '',
                'ticket_number':number,
                'ticket_name':name,
            }
            return res
        else:
            return False
            
    @http.route(['/helpdesk/ticket/tracking'], type='http', auth="public", website=True)
    def helpdek_ticket_tracking(self, **post):
        return request.render("dev_all_in_one_helpdesk_ent.ticket_tracking_page")	
    
    
    
    @http.route(['/my/ticket/<int:inv_id>/accept'], type='json', auth="public", website=True)
    def portal_invoice_accept(self, inv_id, access_token=None, name=None, signature=None):
        # get from query string if not on json param
        access_token = access_token or request.httprequest.args.get('access_token')
        try:
            helpdesk_ticket_sudo = self._document_check_access('helpdesk.ticket', inv_id, access_token=access_token)
        except (AccessError, MissingError):
            return {'error': _('Invalid Ticket.')}

        if not signature:
            return {'error': _('Signature is missing.')}

#        try:
        helpdesk_ticket_sudo.write({
            'object':helpdesk_ticket_sudo,
            'signature_name': name or '',
            'signature_date': fields.Datetime.now(),
            'signature': signature,
        })
        request.env.cr.commit()
        return {
            'force_refresh': True,
            'redirect_url': helpdesk_ticket_sudo.get_portal_url(),
        }

#   
        
        
    @http.route(['/my/ticket/<int:inv_id>/accept'], type='json', auth="public", website=True)
    def portal_invoice_accept(self, inv_id, access_token=None, name=None, signature=None):
        # get from query string if not on json param
        access_token = access_token or request.httprequest.args.get('access_token')
        try:
            helpdesk_ticket_sudo = self._document_check_access('helpdesk.ticket', inv_id, access_token=access_token)
        except (AccessError, MissingError):
            return {'error': _('Invalid Ticket.')}

        if not signature:
            return {'error': _('Signature is missing.')}

#        try:
        helpdesk_ticket_sudo.write({
            'signature_name': name or '',
            'signature_date': fields.Datetime.now(),
            'signature': signature,
        })
        request.env.cr.commit()
        return {
            'force_refresh': True,
            'redirect_url': helpdesk_ticket_sudo.get_portal_url(),
        }	        
    
