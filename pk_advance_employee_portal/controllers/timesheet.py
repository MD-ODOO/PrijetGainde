from datetime import datetime

from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers import portal


class TimesheetPortal(CustomerPortal):
    def _check_timesheet_access_rights(self):
        """
        Custom method to restrict access to CRM portal pages.
        Redirects unauthorized users to /my or 404.
        """
        if not request.env.user.has_group("pk_advance_employee_portal.ad_group_timesheets"):
            return request.not_found()  # or use  request.redirect('/my')if you prefer

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if request.env.user.has_group("pk_advance_employee_portal.ad_group_timesheets"):
            if "timesheet_portal" in counters:
                count = request.env["project.task"].sudo().search_count([])
                values["timesheet_portal"] = count or 1
        return values

    @http.route(['/my/timesheet', '/my/timesheet/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_timesheets(self, page=1, date_start=None, date_end=None, project_id=None, task=None, **kw):
        restrict = self._check_timesheet_access_rights()
        if restrict:
            return restrict

        Employee = request.env["hr.employee"].sudo()
        user = request.env.user
        # Find the employee record for the logged-in user
        employee = Employee.search([("user_id", "=", user.id)], limit=1)
        if not employee:
            return request.render("pk_advance_employee_portal.no_employee_found_template", {})

        Timesheet = request.env['account.analytic.line'].sudo()
        domain = [('employee_id', '=', employee.id)]

        # Apply filters
        if date_start:
            domain.append(('date', '>=', date_start))
        if date_end:
            domain.append(('date', '<=', date_end))
        if project_id:
            domain.append(('project_id', '=', int(project_id)))
        if task:
            domain.append(('task_id.name', 'ilike', task))

        # Pagination setup
        timesheet_count = Timesheet.search_count(domain)
        pager = portal.pager(
            url="/my/timesheet",
            total=timesheet_count,
            page=page,
            step=12,
        )

        # ✅ Order by newest first
        timesheets = Timesheet.search(domain, limit=12, offset=pager['offset'], order="date desc, id desc")

        # ✅ Step 1: Find tasks assigned to this user
        user = request.env.user
        assigned_tasks = request.env['project.task'].sudo().search([
            ('user_ids', 'in', user.id)
        ])

        # ✅ Step 2: Extract unique project records from those tasks
        project_ids = assigned_tasks.mapped('project_id').ids
        projects = request.env['project.project'].sudo().search([('id', 'in', project_ids)])

        values = {
            'timesheets': timesheets,
            'page_name': 'timesheets',
            'pager': pager,
            'projects': projects,
            'date_start': date_start,
            'date_end': date_end,
            'project_id': int(project_id) if project_id else None,
            'task_id': task,
        }
        return request.render('pk_advance_employee_portal.portal_my_timesheets', values)

    @http.route(['/my/ts/create'], type='http', auth="user", website=True, csrf=False)
    def portal_create_timesheet(self, **kw):
        restrict = self._check_timesheet_access_rights()
        if restrict:
            return restrict

        employee = request.env.user.employee_id
        user = request.env.user

        # ✅ Handle POST request (timesheet creation)
        if request.httprequest.method == 'POST':
            #code adapter pour Gainde2000
            project_id = int(kw.get('project_id')) if kw.get(
                'project_id') else False
            task_id = int(kw.get('task_id')) if kw.get('task_id') else False

            # Vérification de sécurité pour Gainde2000
            if task_id:
                task = request.env['project.task'].sudo().browse(task_id)
                if task.project_id.id != project_id:
                    return request.redirect(
                        '/my/timesheet?error=invalid_project_task')
            #
            vals = {
                'date': kw.get('date'),
                'project_id': project_id, #int(kw.get('project_id')) if kw.get('project_id') else False,
                'task_id': task_id, #int(kw.get('task_id')) if kw.get('task_id') else False,
                'name': kw.get('description'),
                'unit_amount': float(kw.get('hours')) if kw.get('hours') else 0.0,
                'employee_id': employee.id,
            }
            request.env['account.analytic.line'].sudo().create(vals)
            return request.redirect('/my/timesheet')

        # ✅ FILTRAGE DYNAMIQUE POUR L'AFFICHAGE

        # 1. Identifier le projet sélectionné (venant de l'URL via onchange JS ou lien)
        selected_project_id = int(kw.get('project_id')) if kw.get(
            'project_id') else False

        # ✅ Step 1: Find tasks assigned to this user
        assigned_tasks = request.env['project.task'].sudo().search([
            ('user_ids', 'in', user.id)
        ])

        # ✅ Step 2: Extract project IDs from those tasks
        #project_ids = assigned_tasks.mapped('project_id').ids
        projects_ids = assigned_tasks.mapped('project_id').ids

        # ✅ Step 3: Fetch only those projects
        projects = request.env['project.project'].sudo().browse(projects_ids)

        # ✅ Step 4: If user selected a project, filter tasks accordingly
        selected_project_id = int(kw.get('project_id')) if kw.get('project_id') else False
        domain = [('user_ids', 'in', user.id)]
        if selected_project_id:
            domain.append(('project_id', '=', selected_project_id))

        tasks = request.env['project.task'].sudo().search(domain)

        return request.render("pk_advance_employee_portal.portal_create_timesheet", {
            'projects': projects,
            'tasks': tasks,
            'selected_project_id': selected_project_id,
        })


    @http.route(['/my/ts/<int:ts_id>'], type='http', auth="user", website=True, csrf=False)
    def view_timesheet(self, ts_id, **kw):
        restrict = self._check_timesheet_access_rights()
        if restrict:
            return restrict

        timesheet = request.env['account.analytic.line'].sudo().browse(ts_id)
        # Security check: only allow the owner to view their own timesheet
        if not timesheet.exists() or timesheet.employee_id.user_id != request.env.user:
            return request.redirect('/my/timesheet')

        return request.render("pk_advance_employee_portal.portal_view_timesheet", {
            'timesheet': timesheet,
        })

    @http.route(['/my/ts/<int:ts_id>/edit'], type='http', auth="user", website=True, csrf=False)
    def edit_timesheet(self, ts_id, **kw):
        restrict = self._check_timesheet_access_rights()
        if restrict:
            return restrict

        user = request.env.user
        employee = user.employee_ids[:1]
        timesheet = request.env['account.analytic.line'].sudo().browse(ts_id)

        # ✅ Security check — ensure timesheet belongs to current user's employee
        if not timesheet.exists() or timesheet.employee_id.user_id != user:
            return request.redirect('/my/timesheet')

        # ✅ Handle POST request
        if request.httprequest.method == 'POST':
            vals = {
                'date': kw.get('date'),
                'project_id': int(kw.get('project_id')) if kw.get('project_id') else False,
                'task_id': int(kw.get('task_id')) if kw.get('task_id') else False,
                'name': kw.get('description'),
                'unit_amount': float(kw.get('hours')) if kw.get('hours') else 0.0,
            }
            timesheet.sudo().write(vals)
            return request.redirect('/my/timesheet')

        # ✅ Get only projects that contain at least one task assigned to this user
        assigned_tasks = request.env['project.task'].sudo().search([('user_ids', 'in', user.id)])
        project_ids = assigned_tasks.mapped('project_id').ids
        projects = request.env['project.project'].sudo().browse(project_ids)

        # ✅ Determine selected project (from timesheet or first available)
        selected_project_id = timesheet.project_id.id if timesheet.project_id else (
            projects[:1].id if projects else False)

        # ✅ Get tasks for selected project, assigned to this user only
        domain = []
        if selected_project_id:
            domain.append(('project_id', '=', selected_project_id))
        domain.append(('user_ids', 'in', user.id))
        tasks = request.env['project.task'].sudo().search(domain)

        return request.render("pk_advance_employee_portal.portal_edit_timesheet", {
            'timesheet': timesheet,
            'projects': projects,
            'tasks': tasks,
            'selected_project_id': selected_project_id,
        })
