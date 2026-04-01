from odoo.addons.portal.controllers import portal
from odoo import http
from odoo.http import request, content_disposition
from odoo.addons.portal.controllers.portal import pager, CustomerPortal


class EmployeePayrollPortal(CustomerPortal):
    def _check_payroll_access_rights(self):
        """
        Custom method to restrict access to Payroll portal pages.
        Redirects unauthorized users to /my or 404.
        """
        if not request.env.user.has_group("pk_advance_employee_portal.ad_group_payroll"):
            return request.not_found()  # or use  request.redirect('/my')if you prefer

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if request.env.user.has_group("pk_advance_employee_portal.ad_group_payroll"):
            if "my_payroll" in counters:
                count = request.env["hr.payslip"].sudo().search_count([])
                values["my_payroll"] = count or 1
        return values

    @http.route(['/my/payslips'], type='http', auth="user", website=True)
    def my_payslips(self,page=1, **kwargs):
        restrict = self._check_payroll_access_rights()
        if restrict:
            return restrict
        Employee = request.env["hr.employee"].sudo()
        user = request.env.user
        # Find the employee record for the logged-in user
        employee = Employee.search([("user_id", "=", user.id)], limit=1)
        if not employee:
            return request.render("pk_advance_employee_portal.no_employee_found_template", {})

        Payslip = request.env['hr.payslip'].sudo()
        employee = request.env.user.employee_id
        domain = [('employee_id', '=', employee.id)]
        payslip_count = Payslip.search_count(domain)
        pager_data = portal.pager(
            url="/my/payslips",
            total=payslip_count,
            page=page,
            step=15
        )
        payslips = Payslip.search(
            domain,
            order='date_from desc',
            limit=15,
            offset=pager_data['offset']
        )
        values = {
            'payslips': payslips,
            'page_name': 'payslips',
            'pager': pager_data,
        }

        return request.render("pk_advance_employee_portal.my_payslips_template", values)

    @http.route(['/my/payslip/<int:payslip_id>/pdf'], type='http', auth="user")
    def portal_print_payslip(self, payslip_id, **kwargs):
        restrict = self._check_payroll_access_rights()
        if restrict:
            return restrict
        # 1. Security check without sudo
        payslip = request.env['hr.payslip'].browse(payslip_id)
        if not payslip or not payslip.exists():
            return request.not_found()
        if payslip.employee_id.user_id != request.env.user:
            return request.not_found()

        # 2. Get the built-in payroll report action
        report_action = request.env.ref('hr_payroll.action_report_payslip').sudo()

        # 3. Generate the PDF for this payslip
        pdf_content, _ = report_action._render_qweb_pdf('hr_payroll.action_report_payslip',res_ids=[payslip.id])

        # 4. Return as downloadable PDF
        pdfhttpheaders = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf_content)),
            ('Content-Disposition', content_disposition(f'Payslip-{payslip.employee_id.name}.pdf')),
        ]
        return request.make_response(pdf_content, headers=pdfhttpheaders)