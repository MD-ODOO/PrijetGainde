from odoo import http
from odoo.http import route, request
from odoo.addons.portal.controllers import portal


class WeeklyCustomerPortal(portal.CustomerPortal):
    def _check_weekly_access_rights(self):
        """
        Custom method to restrict access to Customer portal pages.
        Redirects unauthorized users to /my or 404.
        """
        if not request.env.user.has_group("pk_advance_employee_portal.ad_group_portal_schedule"):
            return request.not_found()  # or use  request.redirect('/my')if you prefer

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if request.env.user.has_group("pk_advance_employee_portal.ad_group_portal_schedule"):
            if "weekly_checkout_count" in counters:
                count = request.env["planning.slot"].sudo().search_count([])
                values["weekly_checkout_count"] = count or 1
        return values

    @route(["/weekly/schedule", "/weekly/schedule/page/<int:page>"],type="http", auth="user", website=True, )
    def portal_weekly_form_view(self, page=1, **kw):
        restrict = self._check_weekly_access_rights()
        if restrict:
            return restrict
        Employee = request.env["hr.employee"].sudo()
        user = request.env.user
        # Find the employee record for the logged-in user
        employee = Employee.search([("user_id", "=", user.id)], limit=1)
        if not employee:
            return request.render("pk_advance_employee_portal.no_employee_found_template", {})

        checkout = request.env["planning.slot"].sudo()
        current_user = request.env.user
        employee = current_user.employee_id

        domain = []
        if employee:
            domain = [('employee_id', '=', employee.id), ('state', '=', 'published')]
        else:
            # fallback for users with no employee linked
            domain = [('employee_id.user_id', '=', current_user.id), ('state', '=', 'published')]

        # Prepare pager data
        checkout_count = checkout.search_count(domain)
        pager_data = portal.pager(
            url="/weekly/schedule",
            total=checkout_count,
            page=page,
            step=15,
        )
        # Recordset according to pager and domain filter
        checkouts = checkout.search(domain, limit=15, offset=pager_data["offset"], )
         # Prepare template values and render
        values = self._prepare_portal_layout_values()

        values.update({"checkouts": checkouts,
                       "page_name": "weekly_schedule",
                       "default_url": "/weekly/schedule",
                       "pager": pager_data,
                       "user": request.env.user})
        return request.render("pk_advance_employee_portal.ad_weekly_schedule_form_view_temp_id", values)

    @http.route(["/weekly/schedule/form/<model('hr.leave'):leave_id>"],type="http", auth="user", website=True)
    def portal_weekly_list_view(self, leave_id, **kw):
        restrict = self._check_weekly_access_rights()
        if restrict:
            return restrict
        vals = {'doc':leave_id, "user": request.env.user}
        return request.render("pk_advance_employee_portal.ad_weekly_schedule_form_view_temp_id", vals)


    # new request form rout
    @http.route(['/weekly-schedule/new'], type='http', auth="user", website=True)
    def portal_weekly_schedule_form(self, **kw):
        restrict = self._check_weekly_access_rights()
        if restrict:
            return restrict
        Employee = request.env["hr.employee"].sudo()
        user = request.env.user
        # Find the employee record for the logged-in user
        employee = Employee.search([("user_id", "=", user.id)], limit=1)
        if not employee:
            return request.render("pk_advance_employee_portal.no_employee_found_template", {})

        return request.render("pk_advance_employee_portal.ad_weekly_schedule__template", {})

    # submit the form rout
    @http.route(['/weekly-schedule/request'], type='http', auth="user", website=True, methods=['POST'], csrf=True)
    def portal_weekly_schedule_submit(self, **post):
        restrict = self._check_weekly_access_rights()
        if restrict:
            return restrict
        resource_id = post.get('resource_id')
        start_datetime = post.get('start_datetime')
        end_datetime = post.get('end_datetime')
        role_id = post.get('role_id')
        company_id = post.get('company_id')

        employee = request.env.user.employee_id

        if employee:
            request.env['planning.slot'].sudo().create({
                'employee_id': employee.id,
                'resource_id': int(resource_id),
                'start_datetime': start_datetime,
                'end_datetime': end_datetime,
                'role_id': int(role_id),
                'company_id': int(company_id),
            })

        return request.redirect('/weekly/schedule')