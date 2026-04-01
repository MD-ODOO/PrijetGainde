import json
from operator import itemgetter

from odoo import conf, http, _, fields
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager

from odoo.tools import groupby as groupbyelem

from odoo.osv.expression import OR, AND


class PurchaseRequestPortal(CustomerPortal):
    PR_MANDATORY_FIELDS = ["date_start", "picking_type_id", "company_id"]
    PR_OPTIONAL_FIELDS = ["name", "requested_by", "origin", "description", "line_ids", "assigned_to"]
    PR_IGNORE_FIELDS = ["product", "qty", "uom", "portal_description"]

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        PurchaseRequest = request.env['purchase.request']
        if 'purchase_requests_count' in counters:
            purchase_requests_count = PurchaseRequest.search_count(self._prepare_purchase_request_domain()) \
                if PurchaseRequest.check_access_rights('read', raise_exception=False) else 0
            values['purchase_requests_count'] = purchase_requests_count if purchase_requests_count else '0'
        return values

    def _prepare_purchase_request_domain(self):
        return [
            ('requested_by', '=', request.env.user.id)
        ]

    @http.route(['/my/purchase_requests', '/my/purchase_requests/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_purchase_request(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, search=None, search_in='all', groupby='none', **kw):
        values = self._prepare_portal_layout_values()
        PurchaseRequest = request.env['purchase.request']

        domain = self._prepare_purchase_request_domain()

        if date_begin and date_end:
            domain += [('date_start', '>', date_begin), ('date_start', '<=', date_end)]
            
        searchbar_sortings = {
            'date': {'label': _('Newest'), 'order': 'date_start desc, id desc'},
            'name': {'label': _('Name'), 'order': 'name asc, id asc'},
        }

        # default sortby order
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        searchbar_inputs = {
            'all': {'input': 'all', 'label': _('Search in all')},
            'name': {'input': 'name', 'label': _('Search in name')},
            'description': {'input': 'description', 'label': _('Search in description')},
            'date_start': {'input': 'date_start', 'label': _('Search in creation date')},
            'requested_by': {'input': 'requested_by', 'label': _('Search in requested by')},
        }

        searchbar_groupby = {
            'none': {'input': 'none', 'label': _('None')},
            'requested_by': {'input': 'requested_by', 'label': _('Requested by')},
        }

        # search
        if search and search_in:
            search_domain = []
            if search_in in ('name', 'all'):
                search_domain = OR([search_domain, [('name', 'ilike', search)]])
            if search_in in ('description', 'all'):
                search_domain = OR([search_domain, [('description', 'ilike', search)]])
            if search_in in ('date_start', 'all'):
                search_domain = OR([search_domain, [('date_start', 'ilike', search)]])
            if search_in in ('requested_by', 'all'):
                search_domain = OR([search_domain, [('requested_by', 'ilike', search)]])
            domain += search_domain

        # count for pager
        purchase_requests_count = PurchaseRequest.search_count(domain)

        # default filter by value
        if not filterby:
            filterby = 'all'

        # make pager
        pager = portal_pager(
            url="/my/purchase_requests",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby, 'filterby': filterby, 'groupby': groupby, 'search_in': search_in, 'search': search},
            total=purchase_requests_count,
            page=page,
            step=self._items_per_page
        )

        if groupby == 'requested_by':
            order = "requested_by, %s" % order

        # search the purchase requests to display, according to the pager data
        purchase_requests = PurchaseRequest.search(
            domain,
            order=order,
            limit=self._items_per_page,
            offset=pager['offset']
        )

        if groupby == 'none':
            grouped_purchase_requests = []
            if purchase_requests:
                grouped_purchase_requests = [purchase_requests]
        else:
            grouped_purchase_requests = [PurchaseRequest.sudo().concat(*g) for k, g in groupbyelem(purchase_requests, itemgetter('requested_by'))]

        request.session['my_purchase_requests_history'] = purchase_requests.ids[:100]
        values.update({
            'date': date_begin,
            'date_end': date_end,
            'purchase_requests': purchase_requests.sudo(),
            'grouped_purchase_requests': grouped_purchase_requests,
            'page_name': 'purchase_request',
            'default_url': '/my/purchase_requests',
            'pager': pager,
            'searchbar_sortings': searchbar_sortings,
            'searchbar_groupby': searchbar_groupby,
            'searchbar_inputs': searchbar_inputs,
            'search_in': search_in,
            'search': search,
            'sortby': sortby,
            'groupby': groupby,
            'filterby': filterby,                        
            'base_url': http.request.env["ir.config_parameter"].sudo().get_param("web.base.url"),
        })
        return request.render("bf_portal_purchase_request.portal_my_purchase_requests", values)
    
    def _pr_get_mandatory_fields(self):
        """ This method is there so that we can override the mandatory fields """
        return self.PR_MANDATORY_FIELDS

    def _pr_get_optional_fields(self):
        """ This method is there so that we can override the optional fields """
        return self.PR_OPTIONAL_FIELDS

    def _pr_get_ignore_fields(self):
        """ This method is there so that we can override the ignore fields """
        return self.PR_IGNORE_FIELDS

    def _pr_details_form_validate(self, data):
        error = dict()
        error_message = []

        # Ignore fields
        for field_name in self._pr_get_ignore_fields():
            if field_name in data:
                data.pop(field_name)

        # Validation
        for field_name in self._pr_get_mandatory_fields():
            if not data.get(field_name):
                error[field_name] = 'missing'

        # error message for empty required fields
        if [err for err in error.values() if err == 'missing']:
            error_message.append(_('Some required fields are empty.'))

        unknown = [k for k in data if k not in self._pr_get_mandatory_fields() + self._pr_get_optional_fields()]
        if unknown:
            error['common'] = 'Unknown field'
            error_message.append("Unknown field '%s'" % ','.join(unknown))

        return error, error_message

    # ------------------------------------------------------------
    # My Purchase Request
    # ------------------------------------------------------------

    def _purchase_request_get_page_view_values(self, pr, access_token, **kwargs):
        values = {
            'page_name': 'purchase_request',
            'purchase_request': pr,
            'can_edit': pr.can_edit(),
            'request_approve': kwargs.get('request_approve', False),
            'request_create': kwargs.get('request_create', False),
        }
        return self._get_page_view_values(pr, access_token, values, 'my_purchase_requests_history', False, **kwargs)

    @http.route([
        '/my/purchase_requests/<int:purchase_request_id>',
        '/my/purchase_requests/<int:purchase_request_id>/<access_token>'], type='http', auth="user", website=True)
    def portal_my_purchase_request_detail(
        self, purchase_request_id, report_type=None, access_token=None, download=False, **post
    ):
        print("post", post)
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
            print("error", error)
            if not error:
                values = {key: post[key] for key in self._pr_get_mandatory_fields()}
                values.update({key: post[key] for key in self._pr_get_optional_fields() if key in post})
                for field in set(['requested_by', 'assigned_to', 'picking_type_id', 'company_id']) & set(values.keys()):
                    try:
                        values[field] = int(values[field])
                    except:
                        values[field] = False
                if values.get("line_ids"):
                    # lines validation
                    line_ids = json.loads(values.get("line_ids"))
                    print("line_ids", line_ids)
                    values.update({'line_ids': line_ids})
                else:
                    values.pop('line_ids', '')
                # Update the purchase request
                print("values", values)
                purchase_request_sudo.write(values)
                # Ya que el log en en chatter solo muestra del bot,
                # se agrega un mensaje para que se vea quien edito
                body = _('Your purchase request has been edited from the portal.')
                purchase_request_sudo.with_context(mail_create_nosubscribe=True).message_post(
                body=body, message_type='comment', subtype_xmlid='mail.mt_note', author_id=request.env.user.partner_id.id)
                return request.redirect('/my/purchase_requests/%s' % (purchase_request_id))

        values.update({
            'users': request.env['res.users'].sudo().search([]),
            'uoms': request.env['uom.uom'].sudo().search([]),
            'companies': request.env.user.company_ids,
            'picking_types': request.env['stock.picking.type'].sudo().search([]),
            'assigned_users': request.env['res.users'].sudo().search([
                ('groups_id', 'in', request.env.ref("purchase_request.group_purchase_request_manager").id)]),
        })

        values.update(self._purchase_request_get_page_view_values(purchase_request_sudo, access_token, **post))
        response = request.render("bf_portal_purchase_request.bf_portal_purchase_request_page", values)
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
        return response

    @http.route(['/my/purchase_requests/new'], type='http', auth="user", website=True)
    def portal_my_purchase_request_new(self, **post):
        purchase_request_sudo = request.env['purchase.request'].sudo()
        print("post", post)

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
            print("error", error)
            if not error:
                values = {key: post[key] for key in self._pr_get_mandatory_fields()}
                values.update({key: post[key] for key in self._pr_get_optional_fields() if key in post})
                for field in set(['requested_by', 'assigned_to', 'picking_type_id', 'company_id']) & set(values.keys()):
                    try:
                        values[field] = int(values[field])
                    except:
                        values[field] = False
                if values.get("line_ids"):
                    # lines validation
                    line_ids = json.loads(values.get("line_ids"))
                    values.update({'line_ids': line_ids})
                else:
                    values.pop('line_ids', '')
                # Update the purchase request
                print("values", values)
                purchase_request_id = purchase_request_sudo.create(values)
                # Ya que el log en en chatter solo muestra del bot,
                # se agrega un mensaje para que se vea quien edito
                body = _('Your purchase request has been created from the portal.')
                purchase_request_id.with_context(mail_create_nosubscribe=True).message_post(
                body=body, message_type='comment', subtype_xmlid='mail.mt_note', author_id=request.env.user.partner_id.id)
                return request.redirect('/my/purchase_requests/%s?request_create=1' % (purchase_request_id.id))

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
            purchase_request_sudo.button_to_approve()
            # Su solicitud de compra a sido enviada desde el portal para ser aprobada.
            body = _('Your purchase request has been sent from the portal for approval.')
            purchase_request_sudo.with_context(mail_create_nosubscribe=True).message_post(
                body=body, message_type='comment', subtype_xmlid='mail.mt_note', author_id=request.env.user.partner_id.id)
            return request.redirect('/my/purchase_requests/%s/%s?request_approve=1' % (purchase_request_id, access_token or ''))
        else:
            return request.redirect('/my')

    @http.route(['/my/purchase_requests/delete/<int:purchase_request_id>',
                 '/my/purchase_requests/delete/<int:purchase_request_id>/<access_token>'], type='http', auth="user", website=True)
    def to_delete(self, purchase_request_id=None, access_token=None, **kw):
        try:
            purchase_request_sudo = self._document_check_access('purchase.request', purchase_request_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        if purchase_request_sudo.state == 'draft':
            purchase_request_sudo.unlink()
        return request.redirect('/my')

    @http.route('/purchase_request/products', type='http', auth="public", methods=['GET'], website=True, sitemap=False)
    def purchase_request_product_read(self, query='', limit=25, **post):
        print("In pruchase_request_product_read")
        data = request.env['product.product'].sudo().search_read(
            domain=['|', ('name', '=ilike', "%" + (query or '') + "%"), ('default_code', '=ilike', "%" + (query or '') + "%")],
            fields=['id', 'display_name', 'uom_id'],
            limit=int(limit),
        )
        return request.make_response(
            json.dumps(data),
            headers=[("Content-Type", "application/json")]
        )

    @http.route('/purchase_request/uoms', type='http', auth="public", methods=['GET'], website=True, sitemap=False)
    def purchase_request_uom_read(self, query='', limit=25, **post):
        uom_env = request.env['uom.uom'].sudo()
        domain = [('name', '=ilike', "%" + (query or '') + "%")]
        if 'uom_id' in post:
            try:
                uom_id = int(post.get('uom_id'))
                category_id = uom_env.browse(uom_id).category_id.id
                domain.append(('category_id', '=', category_id))
            except (ValueError, AttributeError):
                return request.make_response(json.dumps([]), headers=[("Content-Type", "application/json")])
        data = uom_env.search_read(domain=domain, fields=['id', 'display_name'], limit=int(limit))
        return request.make_response(json.dumps(data), headers=[("Content-Type", "application/json")])
