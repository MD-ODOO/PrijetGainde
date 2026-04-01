# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


# =====================================================
# HR FISCAL YEAR
# =====================================================
# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class HrFiscalYear(models.Model):
    _name = "hr.fiscalyear"
    _description = "Fiscal Year"
    _order = "date_start, id"

    name = fields.Char("Exercice", required=True)
    code = fields.Char("Code", size=6, required=True)
    company_id = fields.Many2one(
        'res.company',
        string="Société",
        required=True,
        default=lambda self: self.env.company
    )
    date_start = fields.Date("Date de début", required=True)
    date_stop = fields.Date("Date de fin", required=True)

    period_ids = fields.One2many(
        'hr.period',
        'fiscalyear_id',
        string="Périodes"
    )

    state = fields.Selection(
        [('draft', 'Open'), ('done', 'Closed')],
        default='draft',
        readonly=True
    )

    end_journal_period_id = fields.Many2one(
        'hr.journal.period',
        string="End of Year Entries Journal",
        readonly=True,
        copy=False
    )

    # -------------------------
    # CONSTRAINTS
    # -------------------------
    @api.constrains('date_start', 'date_stop')
    def _check_duration(self):
        for fy in self:
            if fy.date_stop < fy.date_start:
                raise ValidationError(
                    _("The start date of a fiscal year must precede its end date.")
                )

    # -------------------------
    # CREATE PERIODS
    # -------------------------
    def create_period(self, interval=1):
        HrPeriod = self.env['hr.period']

        for fy in self:
            ds = datetime.strptime(str(fy.date_start), '%Y-%m-%d')

            HrPeriod.create({
                'name': _("Opening Period %s") % ds.strftime('%Y'),
                'code': ds.strftime('00/%Y'),
                'date_start': ds.date(),
                'date_stop': ds.date(),
                'special': True,
                'fiscalyear_id': fy.id,
            })

            while ds.strftime('%Y-%m-%d') < str(fy.date_stop):
                de = ds + relativedelta(months=interval, days=-1)
                if de.strftime('%Y-%m-%d') > str(fy.date_stop):
                    de = datetime.strptime(str(fy.date_stop), '%Y-%m-%d')

                HrPeriod.create({
                    'name': ds.strftime('%m/%Y'),
                    'code': ds.strftime('%m/%Y'),
                    'date_start': ds.date(),
                    'date_stop': de.date(),
                    'fiscalyear_id': fy.id,
                })

                ds = ds + relativedelta(months=interval)

    def create_period3(self):
        self.create_period(interval=3)

    # -------------------------
    # FIND
    # -------------------------
    @api.model
    def find(self, date=None):
        date = date or fields.Date.today()

        fy = self.search([
            ('date_start', '<=', date),
            ('date_stop', '>=', date),
            ('company_id', '=', self.env.company.id)
        ], limit=1)

        if not fy:
            raise UserError(
                _("There is no fiscal year defined for this date: %s") % date
            )
        return fy



# =====================================================
# HR PERIOD
# =====================================================
class HrPeriod(models.Model):
    _name = "hr.period"
    _description = "HR Period"
    _order = "date_start, special desc"

    name = fields.Char("Période", required=True)
    code = fields.Char("Code", size=12)
    special = fields.Boolean("Opening/Closing Period")
    date_start = fields.Date("Date de début", required=True)
    date_stop = fields.Date("Date de fin", required=True)

    fiscalyear_id = fields.Many2one(
        'hr.fiscalyear',
        string="Exercice",
        required=True
    )

    company_id = fields.Many2one(
        related='fiscalyear_id.company_id',
        store=True,
        readonly=True
    )

    state = fields.Selection(
        [('draft', 'Ouverte'), ('done', 'Clôturée')],
        default='draft',
        readonly=True
    )

    _sql_constraints = [
        ('name_company_uniq',
         'unique(name, company_id)',
         'The name of the period must be unique per company!')
    ]

    @api.constrains('date_start', 'date_stop')
    def _check_duration(self):
        for rec in self:
            if rec.date_stop < rec.date_start:
                raise ValidationError(_("Invalid period duration"))

    def action_cloture(self):
        for rec in self:
            if rec.fiscalyear_id.state == 'done':
                raise UserError(_("Fiscal year is already closed"))
            rec.state = 'done'

    def action_draft(self):
        for rec in self:
            if rec.fiscalyear_id.state == 'done':
                raise UserError(_("Fiscal year is closed"))
            rec.state = 'draft'


# =====================================================
# HR JOURNAL PERIOD
# =====================================================
class HrJournalPeriod(models.Model):
    _name = "hr.journal.period"
    _description = "Journal Period"
    _order = "period_id"

    name = fields.Char("Journal-Period Name", required=True)
    period_id = fields.Many2one(
        'hr.period',
        string="Period",
        required=True,
        ondelete='cascade'
    )

    state = fields.Selection(
        [('draft', 'Draft'), ('printed', 'Printed'), ('done', 'Done')],
        default='draft',
        readonly=True
    )

    active = fields.Boolean(default=True)

    fiscalyear_id = fields.Many2one(
        related='period_id.fiscalyear_id',
        store=True
    )

    @api.model
    def create(self, vals):
        if vals.get('period_id'):
            period = self.env['hr.period'].browse(vals['period_id'])
            vals['state'] = period.state
        return super().create(vals)
