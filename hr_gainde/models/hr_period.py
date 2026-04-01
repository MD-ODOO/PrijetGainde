# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime
from dateutil.relativedelta import relativedelta

class HrFiscalYear(models.Model):
    _name = "hr.fiscalyear"
    _description = "Fiscal Year"
    _order = "date_start, id"

    name = fields.Char(string="Exercice", required=True)
    code = fields.Char(string="Code", required=True, size=6)
    company_id = fields.Many2one('res.company', string="Société", default=lambda self: self.env.user.company_id)
    date_start = fields.Date(string="Date de début", required=True)
    date_stop = fields.Date(string="Date de fin", required=True)
    period_ids = fields.One2many('hr.period', 'fiscalyear_id', string='Périodes')
    state = fields.Selection([('draft','Open'), ('done','Closed')], string='Status', default='draft', readonly=True, copy=False)
    end_journal_period_id = fields.Many2one('hr.journal.period', string='End of Year Entries Journal', readonly=True, copy=False)

    @api.constrains('date_start', 'date_stop')
    def _check_duration(self):
        for fy in self:
            if fy.date_stop < fy.date_start:
                raise UserError(_('The start date of a fiscal year must precede its end date.'))

    def create_period(self, interval=1):
        Period = self.env['hr.period']
        for fy in self:
            ds = fields.Date.from_string(fy.date_start)
            Period.create({
                'name': "Opening Period %s" % ds.year,
                'code': ds.strftime('00/%Y'),
                'date_start': ds,
                'date_stop': ds,
                'special': True,
                'fiscalyear_id': fy.id,
            })
            while ds.strftime('%Y-%m-%d') < fy.date_stop:
                de = ds + relativedelta(months=interval, days=-1)
                if de.strftime('%Y-%m-%d') > fy.date_stop:
                    de = fields.Date.from_string(fy.date_stop)
                Period.create({
                    'name': ds.strftime('%m/%Y'),
                    'code': ds.strftime('%m/%Y'),
                    'date_start': ds,
                    'date_stop': de,
                    'fiscalyear_id': fy.id,
                })
                ds += relativedelta(months=interval)

    def find(self, dt=None, exception=True):
        return self.finds(dt, exception)[0] if self.finds(dt, exception) else False

    def finds(self, dt=None, exception=True):
        if not dt:
            dt = fields.Date.today()
        domain = [('date_start', '<=', dt), ('date_stop', '>=', dt), ('company_id', '=', self.env.user.company_id.id)]
        fiscalyears = self.search(domain)
        if not fiscalyears and exception:
            raise UserError(_('There is no fiscal year defined for this date: %s.') % dt)
        return fiscalyears

class HrPeriod(models.Model):
    _name = "hr.period"
    _description = "HR Period"
    _order = "date_start, special desc"

    name = fields.Char(string='Période', required=True)
    code = fields.Char(string='Code', size=12)
    special = fields.Boolean(string='Opening/Closing Period', help="These periods can overlap.")
    date_start = fields.Date(string='Période de début', required=True)
    date_stop = fields.Date(string='Période de fin', required=True)
    fiscalyear_id = fields.Many2one('hr.fiscalyear', string='Exercice', required=True)
    state = fields.Selection([('draft','Ouverte'), ('done','Clôturée')], string='Status', default='draft', readonly=True, copy=False)
    company_id = fields.Many2one(related='fiscalyear_id.company_id', string='Company', store=True, readonly=True)

    @api.constrains('date_start', 'date_stop')
    def _check_duration(self):
        for period in self:
            if period.date_stop < period.date_start:
                raise UserError(_('The duration of the Period(s) is invalid.'))

    @api.constrains('date_start', 'date_stop', 'fiscalyear_id')
    def _check_year_limit(self):
        for period in self:
            if period.special:
                continue
            if period.date_start < period.fiscalyear_id.date_start or period.date_stop > period.fiscalyear_id.date_stop:
                raise UserError(_('The period\'s dates are not matching the scope of the fiscal year.'))

    def next(self, step=1):
        periods = self.search([('date_start', '>', self.date_start)])
        return periods[step-1] if len(periods) >= step else False

    def build_ctx_periods(self, period_to_id):
        if self.id == period_to_id:
            return self
        period_from = self
        period_to = self.browse(period_to_id)
        if period_from.company_id != period_to.company_id:
            raise UserError(_('You should choose periods from the same company.'))
        if period_from.date_start > period_to.date_stop:
            raise UserError(_('Start period should precede the end period.'))
        domain = [('date_start', '>=', period_from.date_start), ('date_stop', '<=', period_to.date_stop)]
        if not period_from.special:
            domain.append(('special', '=', False))
        return self.search(domain)

    def action_draft(self):
        for period in self:
            if period.fiscalyear_id.state == 'done':
                raise UserError(_('You cannot re-open a period that belongs to a closed fiscal year.'))
            period.state = 'draft'

    def action_cloture(self):
        for period in self:
            if period.fiscalyear_id.state == 'done':
                raise UserError(_('You cannot close a period that belongs to a closed fiscal year.'))
            period.state = 'done'

class HrJournalPeriod(models.Model):
    _name = "hr.journal.period"
    _description = "Journal Period"
    _order = "period_id"

    name = fields.Char(string='Journal-Period Name', required=True)
    period_id = fields.Many2one('hr.period', string='Period', required=True, ondelete="cascade")
    state = fields.Selection([('draft','Draft'), ('printed','Printed'), ('done','Done')], string='Status', required=True, readonly=True, default='draft')
    active = fields.Boolean(default=True)
    fiscalyear_id = fields.Many2one(related='period_id.fiscalyear_id', string='Fiscal Year', store=True)
    icon = fields.Char(compute='_compute_icon')

    @api.depends('state')
    def _compute_icon(self):
        for r in self:
            r.icon = {
                'draft': 'STOCK_NEW',
                'printed': 'STOCK_PRINT_PREVIEW',
                'done': 'STOCK_DIALOG_AUTHENTICATION',
            }.get(r.state, 'STOCK_NEW')

    @api.model
    def create(self, vals):
        if vals.get('period_id'):
            period = self.env['hr.period'].browse(vals['period_id'])
            vals['state'] = period.state
        return super(HrJournalPeriod, self).create(vals)
