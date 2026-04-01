from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, Command, _, SUPERUSER_ID
from odoo.exceptions import ValidationError, AccessError
from .selection import REQUEST_STATES, DRAFT, DISBURSING, APPROVING, APPROVED, ACCEPTING, \
    ACCEPTED, REJECTED, DISBURSED


class EmployeeLoanRequest(models.Model):
    _name = 'hr.employee.loan.request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _mail_post_access = 'read'
    _description = 'Employee Loan Request'
    _rec_name = 'reference'
    _order = 'date desc'

    @api.model
    def _default_employee_id(self):
        return self.env.user.employee_id

    def _employee_domain(self):
        if self.env.user.has_group('xf_loan.group_xf_loan_officer'):
            return []
        else:
            return [('id', '=', self.env.user.employee_id.id)]
    
   

    reference = fields.Char(
        string='Reference',
        default='/',
        readonly=True,
        copy=False,
    )
    employee_id = fields.Many2one(
        string='Employee',
        comodel_name='hr.employee',
        required=True,
        default=_default_employee_id,
        domain=_employee_domain,
        tracking=True,
    )
    department_id = fields.Many2one(
        string='Department',
        comodel_name='hr.department',
        related='employee_id.department_id',
    )
    job_id = fields.Many2one(
        string='Job Position',
        comodel_name='hr.job',
        related='employee_id.job_id',
    )
    company_id = fields.Many2one(
        string='Company',
        comodel_name='res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        string='Currency',
        comodel_name='res.currency',
        related='company_id.currency_id',
    )
    principal_amount = fields.Monetary(
        string='Principal Amount',
        required=True,
    )
    date = fields.Date(
        string='Date of Request',
        required=True,
        default=fields.Date.context_today,
    )
    num_months = fields.Integer(
        string='Number of Months',
        required=True,
    )
    first_payment_date = fields.Date(
        string='First Payment Date',
        required=True,
    )
    interest_mode = fields.Selection(
        string='Interest Mode',
        selection=[
            ('free', 'Interest-Free'),
            ('flat', 'Flat Interest'),
        ],
        default='free',
    )
    interest_rate = fields.Float(
        string='Interest Rate (%)',
        default=0,
    )
    interest_amount = fields.Monetary(
        string='Interest Amount',
        compute='_compute_interest_amount',
        store=True,
    )
    loan_amount = fields.Monetary(
        string='Loan Amount',
        compute='_compute_loan_amount',
        store=True,
        tracking=True,
    )
    monthly_installment_principal_amount = fields.Monetary(
        string='Monthly Installment Principal Amount',
        compute='_compute_monthly_installment_principal_amount',
        store=True,
    )
    monthly_installment_interest_amount = fields.Monetary(
        string='Monthly Installment Interest Amount',
        compute='_compute_monthly_installment_interest_amount',
        store=True,
    )
    monthly_installment_amount = fields.Monetary(
        string='Monthly Installment Amount',
        compute='_compute_monthly_installment_amount',
        store=True,
    )
    installment_ids = fields.One2many(
        string='Monthly Installments',
        comodel_name='hr.employee.loan.installment',
        inverse_name='loan_request_id',
        readonly=True,
    )
    needs_recomputing = fields.Boolean(
        string='Needs Recomputing',
        compute='_compute_needs_recomputing',
        store=True,
    )
    needs_accepting = fields.Boolean(
        string='Needs Accepting',
        compute='_compute_needs_accepting',
        store=True,
        readonly=False,
    )
    paid_amount = fields.Monetary(
        string='Paid Amount',
        compute='_compute_paid_amount',
        store=True,
    )
    residual_amount = fields.Monetary(
        string='Residual Amount',
        compute='_compute_residual_amount',
        store=True,
    )
    state = fields.Selection(
        string='Status',
        selection=REQUEST_STATES,
        default=DRAFT,
        tracking=True,
        readonly=True,
    )
    is_applicant = fields.Boolean(
        compute='_compute_access_fields',
    )
    can_edit_initial_data = fields.Boolean(
        compute='_compute_access_fields',
    )
    can_edit_accounting_data = fields.Boolean(
        compute='_compute_access_fields',
    )
    can_approve = fields.Boolean(
        compute='_compute_can_approve',
    )
    can_accept = fields.Boolean(
        compute='_compute_access_fields',
    )
    can_reset = fields.Boolean(
        compute='_compute_access_fields',
    )
    initial_data = fields.Json(
        string='Initial Data',
    )

    _initial_data_fields = [
        'loan_amount',
        'num_months',
        'first_payment_date',
    ]

    _sql_constraints = [
        ('check_interest_rate', 'CHECK( interest_rate >= 0 )', 'Interest rate must be greater than or equal to zero.'),
        ('check_num_months', 'CHECK( num_months > 0 )', 'Number of months must be greater than 0.'),
        ('check_principal_amount', 'CHECK( principal_amount > 0 )', 'Principal amount must be greater than 0.'),
    ]

    @api.onchange('interest_mode')
    def _onchange_interest_mode(self):
        if self.interest_mode == 'free':
            self.interest_rate = 0

    def name_get(self):
        result = []
        for record in self:
            name = _('%s for %s') % (record.reference, record.employee_id.name)
            result.append((record.id, name))
        return result

    @api.depends('principal_amount', 'interest_rate')
    def _compute_interest_amount(self):
        for record in self:
            record.interest_amount = record.principal_amount * record.interest_rate / 100

    @api.depends('principal_amount', 'interest_amount')
    def _compute_loan_amount(self):
        for record in self:
            record.loan_amount = record.principal_amount + record.interest_amount

    @api.depends('principal_amount', 'num_months')
    def _compute_monthly_installment_principal_amount(self):
        for record in self:
            if record.num_months > 0:
                record.monthly_installment_principal_amount = record.principal_amount / record.num_months
            else:
                record.monthly_installment_principal_amount = 0

    @api.depends('interest_amount', 'num_months')
    def _compute_monthly_installment_interest_amount(self):
        for record in self:
            if record.num_months > 0:
                record.monthly_installment_interest_amount = record.interest_amount / record.num_months
            else:
                record.monthly_installment_interest_amount = 0

    @api.depends('monthly_installment_principal_amount', 'monthly_installment_interest_amount')
    def _compute_monthly_installment_amount(self):
        for record in self:
            record.monthly_installment_amount = (record.monthly_installment_principal_amount +
                                                 record.monthly_installment_interest_amount)

    @api.depends('installment_ids.paid_amount')
    def _compute_paid_amount(self):
        for record in self:
            record.paid_amount = sum(record.installment_ids.mapped('paid_amount'))

    @api.depends('loan_amount', 'paid_amount')
    def _compute_residual_amount(self):
        for record in self:
            record.residual_amount = record.loan_amount - record.paid_amount

    @api.depends('loan_amount', 'currency_id', 'num_months', 'first_payment_date',
                 'installment_ids', 'installment_ids.amount')
    def _compute_needs_recomputing(self):
        for record in self:
            if not record.installment_ids:
                record.needs_recomputing = True
            else:
                installments_amount = sum(record.installment_ids.mapped('amount'))
                diff_amount = record.currency_id.compare_amounts(record.loan_amount, installments_amount) != 0
                diff_count = record.num_months != len(record.installment_ids)
                diff_date = record.first_payment_date != record.installment_ids[0].date_to_pay
                record.needs_recomputing = diff_amount or diff_count or diff_date

    @api.depends('loan_amount', 'num_months', 'first_payment_date', 'state')
    def _compute_needs_accepting(self):
        for record in self:
            record.needs_accepting = record.state != DRAFT and record._check_if_initial_data_was_changed()

    def _check_if_initial_data_was_changed(self):
        self.ensure_one()
        if not self.initial_data:
            return False
        for field in self._initial_data_fields:
            if str(getattr(self, field)) != self.initial_data.get(field):
                return True
        return False

    @api.constrains('state')
    def _check_state(self):
        for record in self:
            if record.state != DRAFT and record.needs_recomputing:
                raise ValidationError(_('Please compute installments before sending to other stage!'))

    @api.constrains('company_id', 'num_months', 'principal_amount', 'state')
    def _check_limits(self):
        for record in self:
            if record.state == DRAFT:
                continue

            if 0 < record.company_id.max_loan_amount < record.principal_amount:
                raise ValidationError(_('The requested loan amount exceeds the maximum allowed loan amount of %s.') % int(record.company_id.max_loan_amount))
            if 0 < record.company_id.max_num_months < record.num_months:
                raise ValidationError(_('The requested loan term exceeds the maximum allowed loan term of %s month(s).') % record.company_id.max_num_months)

    @api.depends_context('uid')
    @api.depends('state')
    def _compute_can_approve(self):
        is_officer = self.env.user.has_group('xf_loan.group_xf_loan_officer')
        for record in self:
            record.can_approve = record.state == APPROVING and is_officer

    @api.depends_context('uid')
    @api.depends('state')
    def _compute_access_fields(self):
        is_officer = self.env.user.has_group('xf_loan.group_xf_loan_officer')
        is_administrator = self.env.user.has_group('xf_loan.group_xf_loan_administrator')
        for record in self:
            record.is_applicant = record.employee_id.user_id == self.env.user
            if is_officer:
                record.can_edit_initial_data = record.state in (DRAFT, APPROVING)
                record.can_edit_accounting_data = record.state in (DRAFT, APPROVING)
            else:
                record.can_edit_initial_data = record.state in (DRAFT,)
                record.can_edit_accounting_data = False

            record.can_accept = record.state == ACCEPTING and (record.is_applicant or is_administrator)
            record.can_reset = record.state != DRAFT and is_officer

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', '/') == '/':
                seq_date = vals['date'] if 'date' in vals else fields.Date.context_today(self)
                vals['reference'] = self.env['ir.sequence'].next_by_code('employee.loan.request', seq_date)
        records = super(EmployeeLoanRequest, self).create(vals_list)
        return records

    def unlink(self):
        for record in self:
            if record.state != DRAFT:
                raise ValidationError(_('Deletion Restricted: Only draft requests can be deleted!'))
        return super().unlink()

    def _save_initial_data(self):
        for record in self:
            # serialized and save initial data
            record.initial_data = {f: str(getattr(record, f)) for f in self._initial_data_fields}
            # if request was initiated on behalf of other employee
            record.needs_accepting = not record.is_applicant

    def action_generate_installments(self):
        for record in self:
            serial_length = len(str(record.num_months))
            if serial_length < 3:
                serial_length = 3
            sum_installments_principal_amount = 0.0
            sum_installments_interest_amount = 0.0
            installments = [Command.clear()]
            for months in range(record.num_months):
                m_number = months + 1
                date_to_pay = record.first_payment_date + relativedelta(months=months)
                installment_principal_amount = record.monthly_installment_principal_amount
                installment_interest_amount = record.monthly_installment_interest_amount
                if m_number == record.num_months:
                    # To avoid precision issues
                    # If it is the last installment, installment_amount is equal to residual loan amount
                    installment_principal_amount = record.principal_amount - sum_installments_principal_amount
                    installment_interest_amount = record.interest_amount - sum_installments_interest_amount
                sum_installments_principal_amount += installment_principal_amount
                sum_installments_interest_amount += installment_interest_amount
                installments.append(Command.create({
                    'reference': '%s/%s' % (record.reference, str(m_number).zfill(serial_length)),
                    'date_to_pay': date_to_pay,
                    'principal_amount': installment_principal_amount,
                    'interest_amount': installment_interest_amount,
                }))
            record.write({'installment_ids': installments})

            if record.needs_recomputing:
                messages = [
                    _('The specified loan amount cannot be accurately divided by the specified number of months for calculating the monthly installment.'),
                    _('Please enter a different amount or adjust the number of months.')
                ]
                raise ValidationError('\n'.join(messages))

    def action_submit(self):
        self._save_initial_data()
        self.write({'state': APPROVING})

    def action_reset(self):
        self.write({'state': DRAFT, 'initial_data': None, 'needs_accepting': False})

    def action_approve(self):
        for record in self:
            if not record.can_approve:
                raise AccessError(_('You do not have access to approve loan requests!'))
            record.write({'state': APPROVED})
        # Commit changes to track next change of state
        self.env.cr.commit()

        for record in self:
            if record.needs_accepting:
                # If interest rate is greater than zero, we should ask employee if he/she agree with the rate
                record.with_user(SUPERUSER_ID).write({'state': ACCEPTING})
            else:
                record.with_user(SUPERUSER_ID).write({'state': DISBURSING})

    def action_reject(self):
        for record in self:
            if not record.can_approve:
                raise AccessError(_('You do not have access to reject loan requests!'))
            record.write({'state': REJECTED})

    def action_accept(self):
        messages = [
            _('You do not have access to accept the loan request!'),
            _('The loan request must be accepted by the employee who submitted it or by administrator!')
        ]
        for record in self:
            if not record.can_accept:
                raise AccessError('\n'.join(messages))
            record.write({'state': ACCEPTED})
        # Commit changes to track next change of state
        self.env.cr.commit()

        self.with_user(SUPERUSER_ID).write({'state': DISBURSING})

    def _track_subtype(self, init_values):
        self.ensure_one()
        # init_state = self.env.context.get('init_state')
        # if not init_state or init_state not in [state for state, label in REQUEST_STATES]:
        init_state = init_values.get('state')
        if init_state:
            if init_state == DRAFT and self.state == APPROVING:
                return self.env.ref('xf_loan.mt_loan_request_approving')
            if init_state == APPROVING and self.state == APPROVED:
                return self.env.ref('xf_loan.mt_loan_request_approved')
            if init_state == APPROVING and self.state == REJECTED:
                return self.env.ref('xf_loan.mt_loan_request_rejected')
            if init_state == APPROVED and self.state == ACCEPTING:
                return self.env.ref('xf_loan.mt_loan_request_accepting')
            if self.is_applicant and self.state == REJECTED:
                return self.env.ref('xf_loan.mt_loan_request_rejected_by_employee')
            if init_state == ACCEPTING and self.state == ACCEPTED:
                return self.env.ref('xf_loan.mt_loan_request_accepted')

        return super(EmployeeLoanRequest, self)._track_subtype(init_values)


class EmployeeLoanInstallment(models.Model):
    _name = 'hr.employee.loan.installment'
    _description = 'Employee Loan Installment'
    _rec_name = 'reference'
    _order = 'date_to_pay asc'

    reference = fields.Char(
        string='Reference',
        required=True,
        readonly=True,
        copy=False,
    )
    # payslip_id = fields.Many2one(
    #     'hr.payslip',
    #     string="Payslip",
    #     copy=False,
    #     index=True
    # )

    # is_deducted = fields.Boolean(
    #     string="Deducted in Payroll",
    #     default=False,
    #     index=True
    # )

    # def _get_installments_for_payslip(self, employee, date_from, date_to):
    #     return self.search([
    #         ('employee_id', '=', employee.id),
    #         ('state', '=', 'unpaid'),
    #         ('is_deducted', '=', False),
    #         ('date_to_pay', '>=', date_from),
    #         ('date_to_pay', '<=', date_to),
    #         ('loan_request_id.state', 'in', ['disbursing', 'disbursed']),
    #     ], order='date_to_pay asc')

    loan_request_id = fields.Many2one(
        string='Employee Loan Request',
        comodel_name='hr.employee.loan.request',
        required=True,
        ondelete='cascade',
    )
    employee_id = fields.Many2one(
        string='Employee',
        comodel_name='hr.employee',
        related='loan_request_id.employee_id',
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        string='Company',
        comodel_name='res.company',
        related='loan_request_id.company_id',
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        string='Currency',
        comodel_name='res.currency',
        related='loan_request_id.currency_id',
        store=True,
        readonly=True,
    )
    can_paid = fields.Boolean(
        compute='_compute_access_fields',
    )
    date_to_pay = fields.Date(
        string='Date',
        required=True,
    )
    date_payment = fields.Date(
        string='Payment Date',
    )
    principal_amount = fields.Monetary(
        string='Principal Amount',
    )
    interest_amount = fields.Monetary(
        string='Interest Amount',
    )
    amount = fields.Monetary(
        string='Amount',
        compute='_compute_amount',
        store=True,
    )
    paid_principal_amount = fields.Monetary(
        string='Paid Principal Amount',
    )
    paid_interest_amount = fields.Monetary(
        string='Paid Interest Amount',
    )
    paid_amount = fields.Monetary(
        string='Paid Amount',
        compute='_compute_paid_amount',
        store=True,
    )
    state = fields.Selection(
        string='Status',
        selection=[
            ('unpaid', 'Unpaid'),
            ('paid', 'Paid'),
        ],
        compute='_compute_state',
        store=True,
        readonly=True,
    )

    # def _compute_loan_deduction_amount(self, slip, installments):
    
    #     self.ensure_one()

    #     return sum(installments.mapped('amount'))

    @api.depends('principal_amount', 'interest_amount')
    def _compute_amount(self):
        for record in self:
            record.amount = record.principal_amount + record.interest_amount

    @api.depends('paid_principal_amount', 'paid_interest_amount')
    def _compute_paid_amount(self):
        for record in self:
            record.paid_amount = record.paid_principal_amount + record.paid_interest_amount

    def _check_is_paid(self):
        self.ensure_one()
        return self.currency_id.compare_amounts(self.amount, self.paid_amount) == 0

    @api.depends('amount', 'paid_amount')
    def _compute_state(self):
        for record in self:
            state = 'unpaid'
            if record._check_is_paid():
                state = 'paid'
            record.state = state

    def name_get(self):
        result = []
        for record in self:
            name = _('Loan Installment %s') % record.reference
            result.append((record.id, name))
        return result

    @api.depends_context('uid')
    @api.depends('loan_request_id.state')
    def _compute_access_fields(self):
        is_officer = self.env.user.has_group('xf_loan.group_xf_loan_officer')
        for record in self:
            record.can_paid = is_officer and record.loan_request_id.state == DISBURSING

    def action_paid(self, date_payment=None, vals=None):
        if not isinstance(vals, dict):
            vals = {}
        for record in self:
            if not record.can_paid:
                raise AccessError(_('You do not have access to mark installment as paid!'))
            if date_payment is None:
                date_payment = fields.Date.context_today(record)
            vals.update({
                'paid_principal_amount': record.principal_amount,
                'paid_interest_amount': record.interest_amount,
                'date_payment': date_payment,
            })
            record.write(vals)

            loan = record.loan_request_id
            if loan.currency_id.is_zero(loan.residual_amount):
                loan.state = DISBURSED

    def action_unpaid(self, vals=None):
        if not isinstance(vals, dict):
            vals = {}
        for record in self:
            if not record.can_paid:
                raise AccessError(_('You do not have access to mark installment as unpaid!'))
            vals.update({
                'paid_principal_amount': 0,
                'paid_interest_amount': 0,
                'date_payment': None,
            })
            record.write(vals)

            loan = record.loan_request_id
            if not loan.currency_id.is_zero(loan.residual_amount) and loan.state == DISBURSED:
                loan.state = DISBURSING

    def action_reset(self):
        self.write({'state': 'unpaid', 'date_payment': None})

    def _get_by_dates(self, employee, state, date_from, date_to):
        installment_domain = [
            ('loan_request_id.state', 'in', (DISBURSING, DISBURSED)),
            ('employee_id', '=', employee.id),
            ('state', '=', state),
            ('date_to_pay', '>=', date_from),
            ('date_to_pay', '<=', date_to),
        ]
        return self.search(installment_domain)
