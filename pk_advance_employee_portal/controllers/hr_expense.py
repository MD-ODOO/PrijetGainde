import base64
from odoo.addons.portal.controllers import portal
from odoo import http, fields
from odoo.http import request
from _datetime import datetime
from odoo.addons.portal.controllers.portal import pager, CustomerPortal


class MyExpensePortal(CustomerPortal):
    def _check_expense_access_rights(self):
        """
        Custom method to restrict access to Expense portal pages.
        Redirects unauthorized users to /my or 404.
        """
        if not request.env.user.has_group("pk_advance_employee_portal.ad_group_portal_expenses"):
            return request.not_found()  # or use  request.redirect('/my')if you prefer

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if request.env.user.has_group("pk_advance_employee_portal.ad_group_portal_expenses"):
            if "expense_checkout_count" in counters:
                count = request.env["hr.expense"].sudo().search_count([])
                values["expense_checkout_count"] = count or 1
        return values

    @http.route(["/expense/my", "/expense/my/page/<int:page>"], type="http", auth="user", website=True)
    def portal_expense_my_view(self, page=1,date=None, date_end=None, state=None, **kw):
        restrict = self._check_expense_access_rights()
        if restrict:
            return restrict
        Employee = request.env["hr.employee"].sudo()
        user = request.env.user
        # Find the employee record for the logged-in user
        employee = Employee.search([("user_id", "=", user.id)], limit=1)
        if not employee:
            return request.render("pk_advance_employee_portal.no_employee_found_template", {})

        expense_obj = request.env["hr.expense"].sudo()

        # Correct domain filter - using request.env.user instead of uid for clarity
        domain = [('employee_id.user_id', '=', request.env.user.id)]
        if date:
            try:
                date = datetime.strptime(date, "%Y-%m-%d").date()
                domain.append(("date", ">=", date))
            except ValueError:
                pass

        if date_end:
            try:
                date_end = datetime.strptime(date_end, "%Y-%m-%d").date()
                domain.append(("date", "<=", date_end))
            except ValueError:
                pass

            # State filter
        if state:
            domain.append(("state", "=", state))

            # Get state labels for display
        state_labels = dict(
            request.env['hr.expense'].fields_get(allfields=['state'])['state']['selection']
        )

        # Get total count
        checkout_count = expense_obj.search_count(domain)

        # Prepare pager data
        pager_data = portal.pager(
            url="/expense/my",
            total=checkout_count,
            page=page,
            step=15,
        )

        # Get expenses with pagination
        expenses = expense_obj.search(
            domain,
            limit=15,
            offset=pager_data["offset"],
            order='date desc'  # Add sorting
        )

        # Prepare values
        values = {
            'expenses': expenses,
            'page_name': 'expense_my',
            'default_url': '/expense/my',
            'state_labels': state_labels,
            "date": date.strftime("%Y-%m-%d") if date else '',
            "date_end": date_end.strftime("%Y-%m-%d") if date_end else '',
            "state": state,
            'pager': pager_data,
            'user': request.env.user
        }

        # Update with portal layout values
        values.update(self._prepare_portal_layout_values())

        return request.render("pk_advance_employee_portal.ad_portal_my_expenses", values)


    # request new expense
    @http.route('/expense/new', type='http', auth="user", website=True)
    def new_expense_form(self, **kw):
        restrict = self._check_expense_access_rights()
        if restrict:
            return restrict
        # Get products that can be expensed
        products = request.env['product.product'].sudo().search([('can_be_expensed', '=', True)])
        return request.render("pk_advance_employee_portal.ad_expense_submission_form", {
            'products': products,
            'employee': request.env.user.employee_id
        })

    @http.route('/expense/submit', type='http', auth="user", website=True, methods=['POST'], csrf=True)
    def submit_expense(self, **post):
        restrict = self._check_expense_access_rights()
        if restrict:
            return restrict

        import base64
        from odoo.http import request

        # Get and sanitize inputs
        name = post.get('name') or 'Expense'
        product_id_str = post.get('product_id')
        total_amount = float(request.httprequest.form.get('total_amount') or 0.0)
        employee_id = request.env.user.employee_id.id
        description = post.get('description', '')
        payment_mode = post.get('payment_mode')

        # Validate product_id
        if not product_id_str or not product_id_str.isdigit():
            return request.redirect('/expense/new')

        product_id = int(product_id_str)

        # Create the expense
        expense_vals = {
            'name': name,
            'product_id': product_id,
            'total_amount': total_amount,
            'employee_id': employee_id,
            'description': description,
            'payment_mode': payment_mode,
        }
        expense = request.env['hr.expense'].sudo().create(expense_vals)

        # --- Handle multiple file uploads ---
        uploaded_files = request.httprequest.files.getlist('receipts')
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
                        'res_model': 'hr.expense',
                        'res_id': expense.id,
                        'mimetype': file.mimetype,
                    })
                except Exception as e:
                    # Log error but continue with other files
                    request.env['ir.logging'].sudo().create({
                        'name': 'Portal Expense Attachment Error',
                        'type': 'server',
                        'level': 'warning',
                        'message': f'Failed to attach file {file.filename} to expense {expense.id}: {str(e)}',
                        'path': 'portal.expense.submit',
                        'line': '0',
                        'func': 'submit_expense'
                    })

        return request.redirect('/expense/my')

    @http.route('/expense/edit/<int:expense_id>', type='http', auth='user', website=True, methods=['GET', 'POST'],
                csrf=True)
    def edit_expense(self, expense_id, **post):
        restrict = self._check_expense_access_rights()
        if restrict:
            return restrict

        expense = request.env['hr.expense'].sudo().browse(expense_id)
        if not expense.exists() or expense.employee_id.user_id != request.env.user:
            return request.redirect('/expense/my')

        # POST - Save updates
        if request.httprequest.method == 'POST':
            # Get the action parameter FIRST
            action = post.get('action')

            # Handle state change actions that don't require form data update
            if action == 'to_reset':
                try:
                    # Get the expense sheet before removing
                    expense_sheet = expense.sheet_id

                    # Remove expense from sheet
                    if expense_sheet:
                        expense.sudo().write({'sheet_id': False})

                        # If sheet has no more expenses, delete it or reset to draft
                        if not expense_sheet.expense_line_ids:
                            expense_sheet.sudo().unlink()
                        else:
                            # Reset sheet to draft if it has other expenses
                            expense_sheet.sudo().write({'state': 'draft'})

                    # Reset expense to draft
                    expense.sudo().write({'state': 'draft'})

                except Exception as e:
                    request.env['ir.logging'].sudo().create({
                        'name': 'Portal Expense Reset Error',
                        'type': 'server',
                        'level': 'error',
                        'message': f'Failed to reset expense {expense.id} to draft: {str(e)}',
                        'path': 'portal.expense.edit',
                        'line': '0',
                        'func': 'edit_expense'
                    })
                return request.redirect('/expense/my')

            elif action == 'to_refuse':
                try:
                    # Refuse the expense
                    expense.sudo().write({'state': 'refused'})

                    # Also refuse the expense sheet if it exists
                    if expense.sheet_id:
                        expense_sheet = expense.sheet_id

                        # Check if all expenses in the sheet are refused
                        all_refused = all(exp.state == 'refused' for exp in expense_sheet.expense_line_ids)

                        if all_refused:
                            # If all expenses are refused, refuse the entire sheet
                            expense_sheet.sudo().write({'state': 'cancel'})

                except Exception as e:
                    request.env['ir.logging'].sudo().create({
                        'name': 'Portal Expense Refuse Error',
                        'type': 'server',
                        'level': 'error',
                        'message': f'Failed to refuse expense {expense.id}: {str(e)}',
                        'path': 'portal.expense.edit',
                        'line': '0',
                        'func': 'edit_expense'
                    })
                return request.redirect('/expense/my')

            # For update/submit actions, only allow if in draft state
            if expense.state != 'draft':
                return request.redirect(f'/expense/edit/{expense_id}')

            name = post.get('name') or expense.name
            product_id_str = post.get('product_id')
            total_amount = float(request.httprequest.form.get('total_amount') or 0.0)
            description = post.get('description', '')
            payment_mode = post.get('payment_mode')

            if not product_id_str or not product_id_str.isdigit():
                return request.redirect(f'/expense/edit/{expense_id}')

            product_id = int(product_id_str)

            # Update expense data
            expense.sudo().write({
                'name': name,
                'product_id': product_id,
                'total_amount': total_amount,
                'description': description,
                'payment_mode': payment_mode,
            })

            # Handle new file uploads
            uploaded_files = request.httprequest.files.getlist('receipts')
            max_size = 10 * 1024 * 1024  # 10MB in bytes

            for file in uploaded_files:
                if file:
                    try:
                        file_data = base64.b64encode(file.read())

                        # Check file size
                        if len(file_data) > max_size * 1.37:
                            continue

                        request.env['ir.attachment'].sudo().create({
                            'name': file.filename,
                            'type': 'binary',
                            'datas': file_data,
                            'res_model': 'hr.expense',
                            'res_id': expense.id,
                            'mimetype': file.mimetype,
                        })
                    except Exception as e:
                        request.env['ir.logging'].sudo().create({
                            'name': 'Portal Expense Edit Attachment Error',
                            'type': 'server',
                            'level': 'warning',
                            'message': f'Failed to attach file {file.filename} to expense {expense.id}: {str(e)}',
                            'path': 'portal.expense.edit',
                            'line': '0',
                            'func': 'edit_expense'
                        })

            # Perform submit action if requested
            if action == 'draft_submit' and expense.state == 'draft':
                try:
                    # Use Odoo's built-in method to create expense sheet
                    # This automatically creates the sheet and links the expense
                    expense.action_submit_expenses()

                    # After creating the sheet, submit it
                    if expense.sheet_id:
                        expense.sheet_id.action_submit_sheet()

                except Exception as e:
                    request.env['ir.logging'].sudo().create({
                        'name': 'Portal Expense Submit Error',
                        'type': 'server',
                        'level': 'error',
                        'message': f'Failed to submit expense {expense.id}: {str(e)}',
                        'path': 'portal.expense.edit',
                        'line': '0',
                        'func': 'edit_expense'
                    })

            # Redirect after everything is done
            return request.redirect('/expense/my')

        # GET - Render form
        products = request.env['product.product'].sudo().search([('can_be_expensed', '=', True)])
        values = {
            'expense': expense,
            'products': products,
        }
        return request.render('pk_advance_employee_portal.ad_expense_edit_form', values)


    @http.route('/expense/attachment/delete/<int:attachment_id>', type='http', auth='user', website=True, csrf=False)
    def delete_expense_attachment(self, attachment_id, **kw):
        restrict = self._check_expense_access_rights()
        if restrict:
            return restrict
        Attachment = request.env['ir.attachment'].sudo()
        attachment = Attachment.browse(attachment_id)

        if not attachment.exists():
            return request.redirect('/expense/my')

        # Ensure it's linked to an expense
        if attachment.res_model != 'hr.expense' or not attachment.res_id:
            return request.redirect('/expense/my')

        expense = request.env['hr.expense'].sudo().browse(attachment.res_id)
        if expense.state != 'draft':
            return request.render('http_routing.error_message', {
                'error_message': 'Reset to Draft Your request to Edit Attachment'
            })

        # Security: allow only the owner employee to delete
        if not expense.exists() or expense.employee_id.user_id != request.env.user:
            return request.redirect('/expense/my')

        # Perform deletion
        attachment.unlink()

        # ✅ Redirect back to the edit form of that same expense
        return request.redirect(f'/expense/edit/{expense.id}')

