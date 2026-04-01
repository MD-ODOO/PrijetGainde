from datetime import datetime

from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers import portal

class CustomerPortalCRM(CustomerPortal):
    def _check_crm_access_rights(self):
        """
        Custom method to restrict access to CRM portal pages.
        Redirects unauthorized users to /my or 404.
        """
        if not request.env.user.has_group("pk_advance_employee_portal.ad_group_portal_crm"):
            return request.not_found()  # or use  request.redirect('/my')if you prefer

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if request.env.user.has_group("pk_advance_employee_portal.ad_group_portal_crm"):
            if "crm_customer_portal" in counters:
                count = request.env["crm.lead"].sudo().search_count([])
                values["crm_customer_portal"] = count or 1
        return values

    @http.route(['/my/crm', '/my/crm/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_crm(self, page=1, date_start=None, date_end=None, stage_id=None, customer_name=None, **kw):
        restrict = self._check_crm_access_rights()
        if restrict:
            return restrict
        crm_obj = request.env['crm.lead'].sudo()

        # if request.env.user.has_group('base.group_user'):
        #     # Internal user (employee)
        #     domain = [('employee_id.user_id', '=', request.env.user.id)]
        # else:
        #     # External portal customer
        #     domain = [('partner_id', '=', request.env.user.partner_id.id)]

        domain = [('user_id', '=', request.env.user.id)]

        # Date filters
        if date_start:
            try:
                date_start = datetime.strptime(date_start, "%Y-%m-%d").date()
                domain.append(("create_date", ">=", date_start))
            except ValueError:
                pass

        if date_end:
            try:
                date_end = datetime.strptime(date_end, "%Y-%m-%d").date()
                domain.append(("create_date", "<=", date_end))
            except ValueError:
                pass

        # Stage filter
        if stage_id:
            try:
                domain.append(("stage_id", "=", int(stage_id)))
            except ValueError:
                pass

        # --- Customer name filter ---
        if customer_name:
            domain.append(("partner_id.name", "ilike", customer_name))

        # Pager setup
        total_count = crm_obj.search_count(domain)
        pager_data = portal.pager(
            url="/my/crm",
            total=total_count,
            page=page,
            step=15,
            scope=10,
            url_args=kw,
        )

        leads = crm_obj.search(
            domain,
            limit=15,
            offset=pager_data['offset'],
            order='create_date desc'
        )

        # Get available stages
        stages = request.env['crm.stage'].sudo().search([])

        values = {
            'leads': leads,
            'pager': pager_data,
            'stages': stages,
            'stage_id': stage_id,
            'date_start': date_start.strftime("%Y-%m-%d") if date_start else '',
            'date_end': date_end.strftime("%Y-%m-%d") if date_end else '',
            'customer_name': customer_name or '',
        }

        values.update(self._prepare_portal_layout_values())
        return request.render("pk_advance_employee_portal.portal_my_crm", values)


    @http.route(['/my/crm/create'], type='http', auth="user", website=True, csrf=False)
    def portal_create_lead(self, **kw):
        restrict = self._check_crm_access_rights()
        if restrict:
            return restrict
        if kw:
            # Step 1: Create a new customer (partner)
            partner = request.env['res.partner'].sudo().create({
                'name': kw.get('customer_name'),
                'email': kw.get('email_from'),
                'phone': kw.get('phone'),
            })

            # Step 2: Create a new lead linked to that partner
            request.env['crm.lead'].sudo().create({
                'name': kw.get('name'),
                'partner_id': partner.id,  # use the integer ID here
                'expected_revenue': kw.get('expected_revenue'),
                'email_from': kw.get('email_from'),
                'phone': kw.get('phone'),
                'description': kw.get('description'),
                'user_id': request.env.user.id,
            })

            return request.redirect('/my/crm')

        return request.render("pk_advance_employee_portal.portal_create_lead_form")

    @http.route(['/my/crm/<int:lead_id>'], type='http', auth="user", website=True, csrf=False)
    def portal_view_lead(self, lead_id, **kw):
        restrict = self._check_crm_access_rights()
        if restrict:
            return restrict
        lead = request.env['crm.lead'].sudo().browse(lead_id)
        stages = request.env['crm.stage'].sudo().search([])
        if not lead.exists():
            return request.not_found()
        return request.render("pk_advance_employee_portal.portal_view_lead", {'lead': lead, 'stages': stages})

    @http.route(['/my/crm/<int:lead_id>/edit'], type='http', auth="user", website=True)
    def portal_edit_lead(self, lead_id, **kw):
        restrict = self._check_crm_access_rights()
        if restrict:
            return restrict
        Lead = request.env['crm.lead'].sudo()
        lead = Lead.browse(lead_id)
        if not lead.exists():
            return request.not_found()

        stages = request.env['crm.stage'].sudo().search([])

        if kw:
            lead.write({
                'name': kw.get('name'),
                'email_from': kw.get('email_from'),
                'phone': kw.get('phone'),
                'expected_revenue': kw.get('expected_revenue'),
                'description': kw.get('description'),
                'stage_id': int(kw.get('stage_id')) if kw.get('stage_id') else lead.stage_id.id,
            })
            return request.redirect('/my/crm')

        return request.render("pk_advance_employee_portal.portal_my_crm_edit", {
            'lead': lead,
            'stages': stages,
        })

