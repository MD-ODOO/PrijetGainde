# -*- coding: utf-8 -*-
import pytz
from odoo import http, fields
from odoo.http import request
from odoo.addons.portal.controllers import portal
from datetime import datetime, timedelta

class AttendancePortal(portal.CustomerPortal):
    def _check_atta_access_rights(self):
        """
        Custom method to restrict access to Attendance portal pages.
        Redirects unauthorized users to /my or 404.
        """
        if not request.env.user.has_group("pk_advance_employee_portal.ad_group_portal_attendance_access"):
            return request.not_found()  # or use  request.redirect('/my')if you prefer

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if request.env.user.has_group("pk_advance_employee_portal.ad_group_portal_attendance_access"):
            if "attendance_checkin_out" in counters:
                count = request.env["sale.order"].sudo().search_count([])
                values["attendance_checkin_out"] = count or 1
        return values

    _items_per_page = 30  # number of records per page

    @http.route(['/attendance/my', '/attendance/my/page/<int:page>'], type='http', auth='user', website=True)
    def portal_attendance_list(self, page=1, date_start=None, date_end=None, **kw):
        restrict = self._check_atta_access_rights()
        if restrict:
            return restrict
        Employee = request.env["hr.employee"].sudo()
        user = request.env.user
        # Find the employee record for the logged-in user
        employee = Employee.search([("user_id", "=", user.id)], limit=1)
        if not employee:
            return request.render("pk_advance_employee_portal.no_employee_found_template", {})

        domain = [('employee_id', '=', employee.id)]

        # filter by date
        if date_start:
            try:
                date_start = datetime.strptime(date_start, "%Y-%m-%d")
                domain.append(('check_in', '>=', date_start))
            except Exception:
                pass

        if date_end:
            try:
                date_end = datetime.strptime(date_end, "%Y-%m-%d")
                # Include full day by adding 1 day and subtracting 1 second
                date_end = date_end + timedelta(days=1) - timedelta(seconds=1)
                domain.append(('check_in', '<=', date_end))
            except Exception:
                pass

        attendance_model = request.env['hr.attendance'].sudo()
        total_count = attendance_model.search_count(domain)

        pager = portal.pager(
            url="/attendance/my",
            total=total_count,
            page=page,
            step=15,
            scope=7,
            url_args=kw
        )

        records = attendance_model.search(
            domain,
            limit=15,
            offset=pager['offset'],
            order='check_in desc'
        )
        # Find active attendance (not yet checked out)
        active_attendance = attendance_model.search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False)
        ], limit=1)

        values = {
            'attendances': records,
            'pager': pager,
            'date_start': date_start.strftime("%Y-%m-%d") if date_start else '',
            'date_end': date_end.strftime("%Y-%m-%d") if date_end else '',
            'page_name': 'attendance_my',
            'employee': employee,
            'active_attendance': active_attendance,
        }
        user_tz_str = request.env.user.tz or 'UTC'
        user_tz = pytz.timezone(user_tz_str)  # tzinfo object
        values.update({'user_tz': user_tz})

        return request.render("pk_advance_employee_portal.portal_attendance_view", values)


    # --- Punch In ---
    @http.route(['/attendance/check_in'], type='http', auth='user', methods=['POST'], website=True, csrf=False)
    def attendance_check_in(self, **kw):
        restrict = self._check_atta_access_rights()
        if restrict:
            return restrict
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)

        if not employee:
            request.session['warning'] = "Employee record not found."
            return request.redirect('/attendance/my')

        now = fields.Datetime.now()

        # Check if there’s an open attendance (no check_out yet)
        open_attendance = request.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False)
        ], limit=1)

        if open_attendance:
            request.session['warning'] = "You are already checked in! Please check out before starting a new shift."
            return request.redirect('/attendance/my')

        user_agent = request.httprequest.headers.get('User-Agent', 'Unknown')
        ip_address = request.httprequest.remote_addr
        gps_location = kw.get("gps_location")

        lat, lng = (0.0, 0.0)
        if gps_location and "," in gps_location:
            lat, lng = gps_location.split(",")

        request.env['hr.attendance'].sudo().create({
            'employee_id': employee.id,
            'check_in': now,
            'in_browser': user_agent,
            'in_ip_address': ip_address,
            'in_latitude': lat,
            'in_longitude': lng,
            'in_mode': 'kiosk',
        })

        request.session['success'] = "Checked in successfully for a new shift."
        return request.redirect('/attendance/my')

    @http.route(['/attendance/check_out'], type='http', auth='user', methods=['POST'], website=True, csrf=False)
    def attendance_check_out(self, **kw):
        restrict = self._check_atta_access_rights()
        if restrict:
            return restrict
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)
        if not employee:
            return request.redirect('/attendance/my')

        today = fields.Date.context_today(employee)
        today_start = fields.Datetime.to_datetime(str(today) + ' 00:00:00')
        today_end = today_start + timedelta(days=1)

        attendance = request.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', today_start),
            ('check_in', '<', today_end),
            ('check_out', '=', False),
        ], limit=1)

        if not attendance:
            request.session['warning'] = "No active attendance found."
            return request.redirect('/attendance/my')

        gps_location = kw.get("gps_location", "")
        lat = lng = 0.0
        if gps_location and "," in gps_location:
            try:
                lat_str, lng_str = gps_location.split(",", 1)
                lat, lng = float(lat_str), float(lng_str)
            except ValueError:
                pass

        check_out_time = fields.Datetime.now()

        # ✅ If Lunch In exists but Lunch Out missing → auto close lunch
        if attendance.lunch_in and not attendance.lunch_out:
            attendance.sudo().write({
                'lunch_out': check_out_time,
            })

        # ✅ Now perform normal checkout
        attendance.sudo().write({
            'check_out': check_out_time,
            'out_ip_address': request.httprequest.remote_addr,
            'out_browser': request.httprequest.headers.get('User-Agent', 'Unknown'),
            'out_latitude': lat,
            'out_longitude': lng,
            'out_mode': 'kiosk',
        })

        # Force recompute total hours including lunch
        attendance._compute_net_hours()

        return request.redirect('/attendance/my')

    # lunch section
    @http.route(['/attendance/lunch_in'], type='http', auth='user', methods=['POST'], website=True, csrf=False)
    def attendance_lunch_in(self, **post):
        restrict = self._check_atta_access_rights()
        if restrict:
            return restrict
        employee = request.env.user.employee_id
        if not employee:
            request.session['warning'] = "No employee linked to your account."
            return request.redirect('/attendance/my')

        active_attendance = request.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False)
        ], limit=1)

        if not active_attendance:
            request.session['warning'] = "You must check in before starting lunch."
            return request.redirect('/attendance/my')

        if active_attendance.lunch_in:
            request.session['warning'] = "You already started your lunch break."
            return request.redirect('/attendance/my')

        active_attendance.sudo().write({'lunch_in': fields.Datetime.now()})
        request.session['warning'] = "Lunch started successfully."
        return request.redirect('/attendance/my')

    @http.route(['/attendance/lunch_out'], type='http', auth='user', methods=['POST'], website=True, csrf=False)
    def attendance_lunch_out(self, **post):
        restrict = self._check_atta_access_rights()
        if restrict:
            return restrict
        employee = request.env.user.employee_id
        if not employee:
            request.session['warning'] = "No employee linked to your account."
            return request.redirect('/attendance/my')

        active_attendance = request.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False)
        ], limit=1)

        if not active_attendance:
            request.session['warning'] = "You must check in before ending lunch."
            return request.redirect('/attendance/my')

        if not active_attendance.lunch_in:
            request.session['warning'] = "You haven't started your lunch break yet."
            return request.redirect('/attendance/my')

        if active_attendance.lunch_out:
            request.session['warning'] = "You already ended your lunch break."
            return request.redirect('/attendance/my')

        active_attendance.sudo().write({'lunch_out': fields.Datetime.now()})
        request.session['warning'] = "Lunch ended successfully."
        return request.redirect('/attendance/my')