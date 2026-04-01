import base64

from odoo.addons.portal.controllers import portal
from odoo import http, fields
from odoo.fields import Date
from odoo.http import route, request
from odoo.addons.portal.controllers.portal import CustomerPortal
from datetime import datetime


class InheritCustomerPortal(CustomerPortal):
    def _check_timeoff_access_rights(self):
        """
        Custom method to restrict access to Timeoff portal pages.
        Redirects unauthorized users to /my or 404.
        """
        if not request.env.user.has_group("pk_advance_employee_portal.ad_group_portal_leaves"):
            return request.not_found()  # or use  request.redirect('/my')if you prefer

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if request.env.user.has_group("pk_advance_employee_portal.ad_group_portal_leaves"):
            if "book_checkout_count" in counters:
                count = request.env["hr.leave"].sudo().search_count([])
                values["book_checkout_count"] = count or 1
        return values

    @route(["/employee/leaves", "/employee/leaves/page/<int:page>"], type="http", auth="user", website=True)
    def portal_employee_leave_form_view(self, page=1, **kw):
        restrict = self._check_timeoff_access_rights()
        if restrict:
            return restrict
        Employee = request.env["hr.employee"].sudo()
        user = request.env.user
        # Find the employee record for the logged-in user
        employee = Employee.search([("user_id", "=", user.id)], limit=1)
        if not employee:
            return request.render("pk_advance_employee_portal.no_employee_found_template", {})

        # Elevate privileges for hr.leave model operations
        Leave = request.env["hr.leave"].sudo()
        Allocation = request.env["hr.leave.allocation"].sudo()

        domain = [('employee_id', '=', employee.id)]

        # Pagination setup
        checkout_count = Leave.search_count(domain)
        pager_data = portal.pager(
            url="/employee/leaves",
            total=checkout_count,
            page=page,
            step=15,
        )

        # Recordset according to pager and domain filter
        checkouts = Leave.search(domain, limit=15, offset=pager_data["offset"])

        values = self._prepare_portal_layout_values()

        # Validated leaves only
        approved_leaves = Leave.search([('employee_id', '=', employee.id), ('state', '=', 'validate')])

        # Split past and future leaves
        taken_leaves = approved_leaves.filtered(lambda l: l.date_from < fields.Datetime.now())
        scheduled_leaves = approved_leaves.filtered(lambda l: l.date_from >= fields.Datetime.now())

        # Group by type
        leave_types = request.env["hr.leave.type"].sudo().search([])

        taken_leave_days_by_type = {}
        scheduled_leave_days_by_type = {}
        remaining_leave_days_by_type = {}

        for leave_type in leave_types:
            # Allocated days for this type
            allocated = Allocation.search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id', '=', leave_type.id),
                ('state', '=', 'validate')
            ])
            total_allocated = sum(allocated.mapped('number_of_days_display'))

            # Taken days of this type
            taken_days = sum(
                taken_leaves.filtered(lambda l: l.holiday_status_id == leave_type).mapped('number_of_days'))
            scheduled_days = sum(
                scheduled_leaves.filtered(lambda l: l.holiday_status_id == leave_type).mapped('number_of_days'))

            remaining_days = total_allocated - (taken_days + scheduled_days)

            # Save results
            taken_leave_days_by_type[leave_type.name] = taken_days
            scheduled_leave_days_by_type[leave_type.name] = scheduled_days
            if total_allocated > 0:  # show only allocated types
                remaining_leave_days_by_type[leave_type.name] = remaining_days

        # Final values for rendering
        values.update({
            "checkouts": checkouts,
            "page_name": "employee_leave",
            "taken_leave_days_by_type": taken_leave_days_by_type,
            "scheduled_leave_days_by_type": scheduled_leave_days_by_type,
            "remaining_leave_days_by_type": remaining_leave_days_by_type,
            "default_url": "/employee/leaves",
            "pager": pager_data,
            "user": user,
            "employee": employee,
        })

        return request.render("pk_advance_employee_portal.ad_employee_leave_form_view_temp_id", values)


    @http.route(["/employee/leave/<model('hr.leave'):leave_id>"], type="http", auth="user", website=True)
    def portal_employee_leave_list_view(self, leave_id, **kw):
        restrict = self._check_timeoff_access_rights()
        if restrict:
            return restrict

        vals = {'doc': leave_id,
                "user": request.env.user,
                }
        return request.render("pk_advance_employee_portal.ad_employee_leave_list_view_temp_id", vals)


    # create new request template
    @http.route(['/my/leaves/new'], type='http', auth="user", website=True)
    def portal_leave_create_form(self, **kw):
        restrict = self._check_timeoff_access_rights()
        if restrict:
            return restrict

        # Pass leave types with their request_unit to template
        leave_types = request.env['hr.leave.type'].sudo().search([])

        return request.render("pk_advance_employee_portal.ad_portal_leave_create_template", {
            'leave_types': leave_types
        })

    @http.route(['/my/leaves/create'], type='http', auth="user", website=True, methods=['POST'], csrf=True)
    def portal_leave_create_submit(self, **post):
        restrict = self._check_timeoff_access_rights()
        if restrict:
            return restrict

        employee = request.env.user.employee_id
        if not employee:
            return request.render('http_routing.error_message', {
                'error_message': 'You are not linked to an employee record.'
            })

        leave_type_id = post.get('leave_type')
        reason = post.get('reason')

        if not leave_type_id:
            return request.render('http_routing.error_message', {
                'error_message': 'Please select a leave type.'
            })

        # Get the leave type to check request_unit
        leave_type = request.env['hr.leave.type'].sudo().browse(int(leave_type_id))

        try:
            if leave_type.request_unit == 'day':
                # Handle day type
                date_from = post.get('request_date_from')
                date_to = post.get('request_date_to')

                if not (date_from and date_to):
                    return request.render('http_routing.error_message', {
                        'error_message': 'Please fill in all required fields.'
                    })

                # For day type, use Date fields for request_date_from/to
                date_from_date = fields.Date.from_string(date_from)
                date_to_date = fields.Date.from_string(date_to)

                # And Datetime for date_from/to
                date_from_obj = fields.Datetime.from_string(date_from + ' 00:00:00')
                date_to_obj = fields.Datetime.from_string(date_to + ' 23:59:59')
                request_unit_half = False

            elif leave_type.request_unit == 'half_day':
                # Handle half day type
                half_day_date = post.get('half_day_date')
                request_unit_half = post.get('request_unit_half', 'morning')

                if not half_day_date:
                    return request.render('http_routing.error_message', {
                        'error_message': 'Please fill in all required fields.'
                    })

                # For half day, use Date field
                date_from_date = fields.Date.from_string(half_day_date)
                date_to_date = fields.Date.from_string(half_day_date)

                # For half day, set appropriate time based on morning/afternoon
                if request_unit_half == 'morning':
                    date_from_obj = fields.Datetime.from_string(half_day_date + ' 08:00:00')
                    date_to_obj = fields.Datetime.from_string(half_day_date + ' 12:00:00')
                else:  # afternoon
                    date_from_obj = fields.Datetime.from_string(half_day_date + ' 13:00:00')
                    date_to_obj = fields.Datetime.from_string(half_day_date + ' 17:00:00')

            elif leave_type.request_unit == 'hour':
                # Handle hour type
                hour_date_from = post.get('hour_date_from')
                hour_time_from = post.get('hour_time_from')  # String like '11:49'
                hour_date_to = post.get('hour_date_to')
                hour_time_to = post.get('hour_time_to')  # String like '14:30'

                if not all([hour_date_from, hour_time_from, hour_date_to, hour_time_to]):
                    return request.render('http_routing.error_message', {
                        'error_message': 'Please fill in all required fields.'
                    })

                # For hour type, use Date fields
                date_from_date = fields.Date.from_string(hour_date_from)
                date_to_date = fields.Date.from_string(hour_date_to)

                # Combine date and time strings for Datetime fields
                date_from_obj = fields.Datetime.from_string(f'{hour_date_from} {hour_time_from}:00')
                date_to_obj = fields.Datetime.from_string(f'{hour_date_to} {hour_time_to}:00')
                request_unit_half = False

                # Convert time strings to float for Odoo (e.g., '11:30' -> 11.5)
                def time_to_float(time_str):
                    hours, minutes = time_str.split(':')
                    return float(hours) + float(minutes) / 60.0

                hour_time_from_float = time_to_float(hour_time_from)
                hour_time_to_float = time_to_float(hour_time_to)

            else:
                return request.render('http_routing.error_message', {
                    'error_message': 'Invalid leave type configuration.'
                })

        except Exception as e:
            return request.render('http_routing.error_message', {
                'error_message': f'Invalid date or time format: {str(e)}'
            })

        # Create the leave request with proper field types
        leave_vals = {
            'employee_id': employee.id,
            'holiday_status_id': int(leave_type_id),
            'request_date_from': date_from_date,  # Date field
            'request_date_to': date_to_date,  # Date field
            'date_from': date_from_obj,  # Datetime field
            'date_to': date_to_obj,  # Datetime field
            'name': reason or "Leave Request from Portal",
        }

        # Add half-day flag if needed
        if leave_type.request_unit == 'half_day':
            leave_vals['request_unit_half'] = request_unit_half

        # Add hour fields only for hour-type leave
        if leave_type.request_unit == 'hour':
            leave_vals['request_hour_from'] = hour_time_from_float
            leave_vals['request_hour_to'] = hour_time_to_float

        leave_record = request.env['hr.leave'].sudo().create(leave_vals)

        # --- Handle multiple file uploads ---
        uploaded_files = request.httprequest.files.getlist('attachments')
        max_size = 10 * 1024 * 1024  # 10MB in bytes

        for file in uploaded_files:
            if file:
                try:
                    file_data = base64.b64encode(file.read())

                    # Check file size
                    if len(file_data) > max_size * 1.37:  # Base64 encoding increases size by ~37%
                        continue  # Skip files that are too large

                    request.env['ir.attachment'].sudo().create({
                        'name': file.filename,
                        'type': 'binary',
                        'datas': file_data,
                        'res_model': 'hr.leave',
                        'res_id': leave_record.id,
                        'mimetype': file.mimetype,
                    })
                except Exception as e:
                    # Log error but continue with other files
                    request.env['ir.logging'].sudo().create({
                        'name': 'Portal Leave Attachment Error',
                        'type': 'server',
                        'level': 'warning',
                        'message': f'Failed to attach file {file.filename} to leave {leave_record.id}: {str(e)}',
                        'path': 'portal.leave.create',
                        'line': '0',
                        'func': 'portal_leave_create_submit'
                    })

        return request.redirect('/employee/leaves')


    # calendar view rout
    @http.route(['/timeoff/calendar'], type='http', auth='user', website=True)
    def portal_timeoff_calendar(self, **kw):
        restrict = self._check_timeoff_access_rights()
        if restrict:
            return restrict
        """Show calendar of all approved employee leaves"""

        # Get current date
        today = datetime.now().date()

        # Get all validated leaves that haven't ended yet
        leaves = request.env['hr.leave'].sudo().search([
            ('state', 'in', ['validate', 'validate1']),
            ('date_to', '>=', today)  # Only leaves that haven't ended
        ])

        values = {
            'leaves': leaves,
        }
        return request.render('pk_advance_employee_portal.portal_timeoff_calendar_template', values)