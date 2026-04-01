# -*- coding: utf-8 -*-
import logging
from datetime import datetime, time,date
from dateutil.relativedelta import relativedelta
from pytz import timezone
from odoo.exceptions import UserError,ValidationError



from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


# ======================================================
# HR PAYSLIP
# ======================================================
class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    # ------------------------------
    # CHAMPS
    # ------------------------------

    

    #payslip_period_id = fields.Many2one('hr.period', string="Période de paie")

    typePaiement = fields.Selection([
        ('espece', 'Espèces'),
        ('cheque', 'Chèque'),
        ('virement', 'Virement')
    ], string='Type de Paiement',default='virement')

    seniority_year = fields.Integer(compute='_compute_seniority', store=True)
    seniority_month = fields.Integer(compute='_compute_seniority', store=True)
    seniority_char = fields.Char(compute='_compute_seniority', store=True)

    nb_part_of_payslip = fields.Float(string='Nombre de Part IR',store=True)
    trimf = fields.Float(string='Trimf',store=True)
    total_brut_annuel = fields.Float(compute='_compute_total_brut_annuel', store=True)
    amount_net = fields.Float(string="Net à payer", store=True)

    employee_bank_id = fields.Many2one('hr.bank.employee')
   

    # ------------------------------
    # ONCHANGE PERIODE
    # ------------------------------
    @api.onchange('payslip_period_id')
    def _onchange_period(self):
        if self.payslip_period_id:
            self.date_from = self.payslip_period_id.date_start
            self.date_to = self.payslip_period_id.date_stop

    # ------------------------------
    # ANCIENNETE
    # ------------------------------
    @api.depends('contract_id', 'date_to')
    def _compute_seniority(self):
        for slip in self:
            slip.seniority_year = 0
            slip.seniority_month = 0
            slip.seniority_char = ''
            slip.nb_part_of_payslip = 0

            if slip.contract_id and slip.contract_id.date_start and slip.date_to:
                delta = relativedelta(slip.date_to, slip.contract_id.date_start)
                slip.seniority_year = delta.years
                slip.seniority_month = delta.months
                slip.seniority_char = f"{delta.years} an(s) {delta.months} mois {delta.days} jours"
                slip.nb_part_of_payslip = slip.employee_id.nb_part or 1
                slip.trimf = slip.employee_id.trimf or 1

    # ------------------------------
    # TOTAL BRUT ANNUEL
    # ------------------------------
    @api.depends('line_ids')
    def _compute_total_brut_annuel(self):
        for slip in self:
            total = 0.0
            payslips = self.env['hr.payslip'].search([
                ('employee_id', '=', slip.employee_id.id),
                ('state', '=', 'done')
            ], order='date_from desc', limit=12)

            for ps in payslips:
                total += sum(ps.line_ids.filtered(
                    lambda l: l.code in ('BASIC', 'BRUT')
                ).mapped('total'))

            slip.total_brut_annuel = total

    # ------------------------------
    # WORKED DAYS (OBLIGATOIRE)
    # ------------------------------
    # @api.model
    # def get_worked_day_lines(self, contracts, date_from, date_to):
    #     """
    #     Reprise fonctionnelle de ton code legacy
    #     Compatible Odoo 18
    #     """
    #     res = []

    #     for contract in contracts.filtered(lambda c: c.resource_calendar_id):
    #         calendar = contract.resource_calendar_id
    #         tz = timezone(calendar.tz or 'UTC')

    #         day_from = datetime.combine(date_from, time.min)
    #         day_to = datetime.combine(date_to, time.max)

    #         # --------------------------
    #         # CONGES
    #         # --------------------------
    #         leaves = {}
    #         day_leave_intervals = contract.employee_id.list_leaves(
    #             day_from, day_to, calendar=calendar
    #         )

    #         for day, hours, leave in day_leave_intervals:
    #             holiday = leave.holiday_id
    #             status = holiday.holiday_status_id

    #             leave_line = leaves.setdefault(status.id, {
    #                 'name': status.name or _('Congés'),
    #                 'sequence': 5,
    #                 'code': status.code or 'LEAVE',
    #                 'number_of_days': 0.0,
    #                 'number_of_hours': 0.0,
    #                 'contract_id': contract.id,
    #             })

    #             leave_line['number_of_hours'] -= hours

    #             work_hours = calendar.get_work_hours_count(
    #                 tz.localize(datetime.combine(day, time.min)),
    #                 tz.localize(datetime.combine(day, time.max)),
    #                 compute_leaves=False,
    #             )
    #             if work_hours:
    #                 leave_line['number_of_days'] -= hours / work_hours

    #         # --------------------------
    #         # JOURS TRAVAILLES
    #         # --------------------------
    #         work_data = contract.employee_id._get_work_days_data(
    #             day_from,
    #             day_to,
    #             calendar=calendar,
    #             compute_leaves=False,
    #         )

    #         res.append({
    #             'name': _("Jours travaillés"),
    #             'sequence': 1,
    #             'code': 'WORK100',
    #             'number_of_days': work_data['days'],
    #             'number_of_hours': work_data['hours'],
    #             'contract_id': contract.id,
    #         })

    #         res.extend(leaves.values())

    #     return res

    # ------------------------------
    # NET A PAYER
    # ------------------------------
    def get_payslip_lines(self, cr, uid, contract_ids, payslip_id, context):
        def _sum_salary_rule_category(localdict, category, amount):
            if category.parent_id:
                localdict = _sum_salary_rule_category(localdict, category.parent_id, amount)
            localdict['categories'].dict[category.code] = category.code in localdict['categories'].dict and \
                                                          localdict['categories'].dict[category.code] + amount or amount
            return localdict

        class BrowsableObject(object):
            def __init__(self, pool, cr, uid, employee_id, dict):
                self.pool = pool
                self.cr = cr
                self.uid = uid
                self.employee_id = employee_id
                self.dict = dict

            def __getattr__(self, attr):
                return attr in self.dict and self.dict.__getitem__(attr) or 0.0

        class InputLine(BrowsableObject):
            """a class that will be used into the python code, mainly for usability purposes"""

            def sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = datetime.now().strftime('%Y-%m-%d')
                result = 0.0
                self.cr.execute("SELECT sum(amount) as sum\
                            FROM hr_payslip as hp, hr_payslip_input as pi \
                            WHERE hp.employee_id = %s AND hp.state = 'done' \
                            AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pi.payslip_id AND pi.code = %s",
                                (self.employee_id, from_date, to_date, code))
                res = self.cr.fetchone()[0]
                return res or 0.0

        class WorkedDays(BrowsableObject):
            """a class that will be used into the python code, mainly for usability purposes"""

            def _sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = datetime.now().strftime('%Y-%m-%d')
                result = 0.0
                self.cr.execute("SELECT sum(number_of_days) as number_of_days, sum(number_of_hours) as number_of_hours\
                            FROM hr_payslip as hp, hr_payslip_worked_days as pi \
                            WHERE hp.employee_id = %s AND hp.state = 'done'\
                            AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pi.payslip_id AND pi.code = %s",
                                (self.employee_id, from_date, to_date, code))
                return self.cr.fetchone()

            def sum(self, code, from_date, to_date=None):
                res = self._sum(code, from_date, to_date)
                return res and res[0] or 0.0

            def sum_hours(self, code, from_date, to_date=None):
                res = self._sum(code, from_date, to_date)
                return res and res[1] or 0.0

        class Payslips(BrowsableObject):
            """a class that will be used into the python code, mainly for usability purposes"""

            def sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = datetime.now().strftime('%Y-%m-%d')
                self.cr.execute("SELECT sum(case when hp.credit_note = False then (pl.total) else (-pl.total) end)\
                            FROM hr_payslip as hp, hr_payslip_line as pl \
                            WHERE hp.employee_id = %s AND hp.state = 'done' \
                            AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pl.slip_id AND pl.code = %s",
                                (self.employee_id, from_date, to_date, code))
                res = self.cr.fetchone()
                return res and res[0] or 0.0

        # we keep a dict with the result because a value can be overwritten by another rule with the same code
        result_dict = {}
        rules = {}
        categories_dict = {}
        blacklist = []
        payslip_obj = self.pool.get('hr.payslip')
        inputs_obj = self.pool.get('hr.payslip.worked_days')
        obj_rule = self.pool.get('hr.salary.rule')
        payslip = payslip_obj.browse(cr, uid, payslip_id, context=context)
        worked_days = {}
        for worked_days_line in payslip.worked_days_line_ids:
            worked_days[worked_days_line.code] = worked_days_line
        inputs = {}
        for input_line in payslip.input_line_ids:
            inputs[input_line.code] = input_line

        categories_obj = BrowsableObject(self.pool, cr, uid, payslip.employee_id.id, categories_dict)
        input_obj = InputLine(self.pool, cr, uid, payslip.employee_id.id, inputs)
        worked_days_obj = WorkedDays(self.pool, cr, uid, payslip.employee_id.id, worked_days)
        payslip_obj = Payslips(self.pool, cr, uid, payslip.employee_id.id, payslip)
        rules_obj = BrowsableObject(self.pool, cr, uid, payslip.employee_id.id, rules)

        baselocaldict = {'categories': categories_obj, 'rules': rules_obj, 'payslip': payslip_obj,
                         'worked_days': worked_days_obj, 'inputs': input_obj}
        # get the ids of the structures on the contracts and their parent id as well
        structure_ids = self.pool.get('hr.contract').get_all_structures(cr, uid, contract_ids, context=context)
        # get the rules of the structure and thier children
        rule_ids = self.pool.get('hr.payroll.structure').get_all_rules(cr, uid, structure_ids, context=context)
        # run the rules by sequence
        sorted_rule_ids = [id for id, sequence in sorted(rule_ids, key=lambda x: x[1])]

        rules_for_end_contract_provision = ['C1000', 'C1010', 'C1020', 'C1043', 'C1047', 'C1076', 'C1078', 'C1079',
                                            'C1080', 'C1090']
        global_value_for_allowance = 0.0
        rule_for_holiday_provision = ['C1000', 'C1010', 'C1115', 'C1020', 'C1043', 'C1076', 'C1078', 'C1079', 'C1080']
        global_value_for_holiday_provision = 0.0

        for contract in self.pool.get('hr.contract').browse(cr, uid, contract_ids, context=context):
            employee = contract.employee_id
            localdict = dict(baselocaldict, employee=employee, contract=contract)
            for rule in obj_rule.browse(cr, uid, sorted_rule_ids, context=context):
                key = rule.code + '-' + str(contract.id)
                localdict['result'] = None
                localdict['result_qty'] = 1.0
                localdict['result_rate'] = 100
                # check if the rule can be applied
                if obj_rule.satisfy_condition(cr, uid, rule.id, localdict,
                                              context=context) and rule.id not in blacklist:
                    # compute the amount of the rule
                    amount, qty, rate = obj_rule.compute_rule(cr, uid, rule.id, localdict, context=context)

                    if rule.code in rules_for_end_contract_provision:
                        global_value_for_allowance += amount

                    if rule.code in rule_for_holiday_provision:
                        global_value_for_holiday_provision += amount

                    if rule.code == 'C1040':  # indemnite de fin de contrat
                        amount = payslip.compute_end_contract_allowance(global_value_for_allowance)
                    elif rule.code == 'C1145':  # indemnite de licenciement
                        amount = payslip.compute_retirement_balance(global_value_for_allowance)
                    elif rule.code == 'C1146':  # indemnite de deces
                        amount = payslip.compute_retirement_balance(global_value_for_allowance)
                    elif rule.code == 'C1110':  # provision de retraite
                        amount = payslip.compute_provision_retraite(global_value_for_allowance)
                    elif rule.code == 'C1120':  # indemnité de retraite
                        amount = payslip.compute_retirement_balance(global_value_for_allowance)
                    elif rule.code == 'C1150':  # provision conges
                        amount = round(global_value_for_holiday_provision / 24)
                    else:
                        pass
                    # check if there is already a rule computed with that code
                    previous_amount = rule.code in localdict and localdict[rule.code] or 0.0
                    # set/overwrite the amount computed for this rule in the localdict
                    tot_rule = amount * qty * rate / 100.0
                    localdict[rule.code] = tot_rule
                    rules[rule.code] = rule
                    # sum the amount for its salary category
                    localdict = _sum_salary_rule_category(localdict, rule.category_id, tot_rule - previous_amount)
                    # create/overwrite the rule in the temporary results
                    result_dict[key] = {
                        'salary_rule_id': rule.id,
                        'contract_id': contract.id,
                        'name': rule.name,
                        'code': rule.code,
                        'category_id': rule.category_id.id,
                        'sequence': rule.sequence,
                        'appears_on_payslip': rule.appears_on_payslip,
                        'condition_select': rule.condition_select,
                        'condition_python': rule.condition_python,
                        'condition_range': rule.condition_range,
                        'condition_range_min': rule.condition_range_min,
                        'condition_range_max': rule.condition_range_max,
                        'amount_select': rule.amount_select,
                        'amount_fix': rule.amount_fix,
                        'amount_python_compute': rule.amount_python_compute,
                        'amount_percentage': rule.amount_percentage,
                        'amount_percentage_base': rule.amount_percentage_base,
                        'register_id': rule.register_id.id,
                        'amount': amount,
                        'employee_id': contract.employee_id.id,
                        'quantity': qty,
                        'rate': rate,
                    }
                else:
                    # blacklist this rule and its children
                    blacklist += [id for id, seq in
                                  self.pool.get('hr.salary.rule')._recursive_search_of_rules(cr, uid, [rule],
                                                                                             context=context)]

        result = [value for code, value in result_dict.items()]
        return result

    def get_payslip_lines(self, cr, uid, contract_ids, payslip_id, context):
        def _sum_salary_rule_category(localdict, category, amount):
            if category.parent_id:
                localdict = _sum_salary_rule_category(localdict, category.parent_id, amount)
            localdict['categories'].dict[category.code] = category.code in localdict['categories'].dict and \
                                                          localdict['categories'].dict[category.code] + amount or amount
            return localdict

        class BrowsableObject(object):
            def __init__(self, pool, cr, uid, employee_id, dict):
                self.pool = pool
                self.cr = cr
                self.uid = uid
                self.employee_id = employee_id
                self.dict = dict

            def __getattr__(self, attr):
                return attr in self.dict and self.dict.__getitem__(attr) or 0.0

        class InputLine(BrowsableObject):
            """a class that will be used into the python code, mainly for usability purposes"""

            def sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = datetime.now().strftime('%Y-%m-%d')
                result = 0.0
                self.cr.execute("SELECT sum(amount) as sum\
                            FROM hr_payslip as hp, hr_payslip_input as pi \
                            WHERE hp.employee_id = %s AND hp.state = 'done' \
                            AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pi.payslip_id AND pi.code = %s",
                                (self.employee_id, from_date, to_date, code))
                res = self.cr.fetchone()[0]
                return res or 0.0

        class WorkedDays(BrowsableObject):
            """a class that will be used into the python code, mainly for usability purposes"""

            def _sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = datetime.now().strftime('%Y-%m-%d')
                result = 0.0
                self.cr.execute("SELECT sum(number_of_days) as number_of_days, sum(number_of_hours) as number_of_hours\
                            FROM hr_payslip as hp, hr_payslip_worked_days as pi \
                            WHERE hp.employee_id = %s AND hp.state = 'done'\
                            AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pi.payslip_id AND pi.code = %s",
                                (self.employee_id, from_date, to_date, code))
                return self.cr.fetchone()

            def sum(self, code, from_date, to_date=None):
                res = self._sum(code, from_date, to_date)
                return res and res[0] or 0.0

            def sum_hours(self, code, from_date, to_date=None):
                res = self._sum(code, from_date, to_date)
                return res and res[1] or 0.0

        class Payslips(BrowsableObject):
            """a class that will be used into the python code, mainly for usability purposes"""

            def sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = datetime.now().strftime('%Y-%m-%d')
                self.cr.execute("SELECT sum(case when hp.credit_note = False then (pl.total) else (-pl.total) end)\
                            FROM hr_payslip as hp, hr_payslip_line as pl \
                            WHERE hp.employee_id = %s AND hp.state = 'done' \
                            AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pl.slip_id AND pl.code = %s",
                                (self.employee_id, from_date, to_date, code))
                res = self.cr.fetchone()
                return res and res[0] or 0.0

        # we keep a dict with the result because a value can be overwritten by another rule with the same code
        result_dict = {}
        rules = {}
        categories_dict = {}
        blacklist = []
        payslip_obj = self.pool.get('hr.payslip')
        inputs_obj = self.pool.get('hr.payslip.worked_days')
        obj_rule = self.pool.get('hr.salary.rule')
        payslip = payslip_obj.browse(cr, uid, payslip_id, context=context)
        worked_days = {}
        for worked_days_line in payslip.worked_days_line_ids:
            worked_days[worked_days_line.code] = worked_days_line
        inputs = {}
        for input_line in payslip.input_line_ids:
            inputs[input_line.code] = input_line

        categories_obj = BrowsableObject(self.pool, cr, uid, payslip.employee_id.id, categories_dict)
        input_obj = InputLine(self.pool, cr, uid, payslip.employee_id.id, inputs)
        worked_days_obj = WorkedDays(self.pool, cr, uid, payslip.employee_id.id, worked_days)
        payslip_obj = Payslips(self.pool, cr, uid, payslip.employee_id.id, payslip)
        rules_obj = BrowsableObject(self.pool, cr, uid, payslip.employee_id.id, rules)

        baselocaldict = {'categories': categories_obj, 'rules': rules_obj, 'payslip': payslip_obj,
                         'worked_days': worked_days_obj, 'inputs': input_obj}
        # get the ids of the structures on the contracts and their parent id as well
        structure_ids = self.pool.get('hr.contract').get_all_structures(cr, uid, contract_ids, context=context)
        # get the rules of the structure and thier children
        rule_ids = self.pool.get('hr.payroll.structure').get_all_rules(cr, uid, structure_ids, context=context)
        # run the rules by sequence
        sorted_rule_ids = [id for id, sequence in sorted(rule_ids, key=lambda x: x[1])]

        rules_for_end_contract_provision = ['C1000', 'C1010', 'C1020', 'C1043', 'C1047', 'C1076', 'C1078', 'C1079',
                                            'C1080', 'C1090']
        global_value_for_allowance = 0.0
        rule_for_holiday_provision = ['C1000', 'C1010', 'C1115', 'C1020', 'C1043', 'C1076', 'C1078', 'C1079', 'C1080']
        global_value_for_holiday_provision = 0.0

        for contract in self.pool.get('hr.contract').browse(cr, uid, contract_ids, context=context):
            employee = contract.employee_id
            localdict = dict(baselocaldict, employee=employee, contract=contract)
            for rule in obj_rule.browse(cr, uid, sorted_rule_ids, context=context):
                key = rule.code + '-' + str(contract.id)
                localdict['result'] = None
                localdict['result_qty'] = 1.0
                localdict['result_rate'] = 100
                # check if the rule can be applied
                if obj_rule.satisfy_condition(cr, uid, rule.id, localdict,
                                              context=context) and rule.id not in blacklist:
                    # compute the amount of the rule
                    amount, qty, rate = obj_rule.compute_rule(cr, uid, rule.id, localdict, context=context)

                    if rule.code in rules_for_end_contract_provision:
                        global_value_for_allowance += amount

                    if rule.code in rule_for_holiday_provision:
                        global_value_for_holiday_provision += amount

                    if rule.code == 'C1040':  # indemnite de fin de contrat
                        amount = payslip.compute_end_contract_allowance(global_value_for_allowance)
                    elif rule.code == 'C1145':  # indemnite de licenciement
                        amount = payslip.compute_retirement_balance(global_value_for_allowance)
                    elif rule.code == 'C1146':  # indemnite de deces
                        amount = payslip.compute_retirement_balance(global_value_for_allowance)
                    elif rule.code == 'C1110':  # provision de retraite
                        amount = payslip.compute_provision_retraite(global_value_for_allowance)
                    elif rule.code == 'C1120':  # indemnité de retraite
                        amount = payslip.compute_retirement_balance(global_value_for_allowance)
                    elif rule.code == 'C1150':  # provision conges
                        amount = round(global_value_for_holiday_provision / 24)
                    else:
                        pass
                    # check if there is already a rule computed with that code
                    previous_amount = rule.code in localdict and localdict[rule.code] or 0.0
                    # set/overwrite the amount computed for this rule in the localdict
                    tot_rule = amount * qty * rate / 100.0
                    localdict[rule.code] = tot_rule
                    rules[rule.code] = rule
                    # sum the amount for its salary category
                    localdict = _sum_salary_rule_category(localdict, rule.category_id, tot_rule - previous_amount)
                    # create/overwrite the rule in the temporary results
                    result_dict[key] = {
                        'salary_rule_id': rule.id,
                        'contract_id': contract.id,
                        'name': rule.name,
                        'code': rule.code,
                        'category_id': rule.category_id.id,
                        'sequence': rule.sequence,
                        'appears_on_payslip': rule.appears_on_payslip,
                        'condition_select': rule.condition_select,
                        'condition_python': rule.condition_python,
                        'condition_range': rule.condition_range,
                        'condition_range_min': rule.condition_range_min,
                        'condition_range_max': rule.condition_range_max,
                        'amount_select': rule.amount_select,
                        'amount_fix': rule.amount_fix,
                        'amount_python_compute': rule.amount_python_compute,
                        'amount_percentage': rule.amount_percentage,
                        'amount_percentage_base': rule.amount_percentage_base,
                        'register_id': rule.register_id.id,
                        'amount': amount,
                        'employee_id': contract.employee_id.id,
                        'quantity': qty,
                        'rate': rate,
                    }
                else:
                    # blacklist this rule and its children
                    blacklist += [id for id, seq in
                                  self.pool.get('hr.salary.rule')._recursive_search_of_rules(cr, uid, [rule],
                                                                                             context=context)]

        result = [value for code, value in result_dict.items()]
        return result

    def compute_sheet(self):
        super().compute_sheet()
        for slip in self:
            slip.amount_net = sum(
                slip.line_ids.filtered(lambda l: l.code == 'NET').mapped('total')
            )


# ======================================================
# HR PAYSLIP LINE
# ======================================================
class HrPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    payslip_date_from = fields.Date(string='Date Début',related='slip_id.date_from', store=True)
    payslip_date_to = fields.Date(string='Date Fin',related='slip_id.date_to', store=True)

    # matricule = fields.Char(related='employee_id.otherid', store=True)
    # gender = fields.Selection(related='employee_id.gender', store=True)
    typePaiement = fields.Selection(related='slip_id.typePaiement', store=True)
    




class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'

    def _get_default_rule_ids(self):
        """
        Charger uniquement les règles salariales
        sans ouvrir le formulaire
        et sans héritage indésirable
        """
        rules = self.env['hr.salary.rule'].search([
            ('parent_id', '=', False),
            ('active', '=', True),
        ], order='sequence')

        return [
            (0, 0, {
                'name': rule.name,
                'sequence': rule.sequence,
                'code': rule.code,
                'category_id': rule.category_id.id,
                'condition_select': rule.condition_select,
                'condition_python': rule.condition_python,
                'amount_select': rule.amount_select,
                'amount_python_compute': rule.amount_python_compute,
                'appears_on_employee_cost_dashboard': rule.appears_on_employee_cost_dashboard,
            })
            for rule in rules
        ]
        
class CompanyCfec(models.Model):
    _name = 'company.cfce'
    

    name = fields.Float( string="Valeur CFCE",required=True,default=3)
    plafond_cadre = fields.Float( string="Ipres Plafond CADRE",required=True,default=1296000)
    plafond_general = fields.Float( string="Ipres Plafond CADRE",required=True,default=432000)
    
class PrimeAttribution(models.Model):
    _name = 'prime.attribution'
    

    name = fields.Char(
    string="Référence",
    readonly=True,
    copy=False,
    default="Nouveau"
)
    date_fin = fields.Date( string="Date Fin",required=True)
    date_debut = fields.Date(
        string="Date début",
        required=True,
        default=fields.Date.today
    )
    categ_id = fields.Many2one('hr.categ.prime', string="Catégorie",required=True)
    type_prime= fields.Selection([
        ('religieuse', 'Reliegieuse'),
        ('tech', 'Technique'),
        ('13eme', '13ème Mois'),
        ('iso', 'Prime Iso')

    ], string='Type de prime',required=True)
    
    valeur_prime=fields.Float('Valeur Prime',required=True)
    
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('active', 'Active'),
        ('expired', 'Expirée'),
        ('cancelled', 'Annulée'),
    ], compute="_compute_state", store=False)
    
    active = fields.Boolean(default=True)
    
    manual_state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('cancelled', 'Annulé'),
    ], default='draft')
    
    employee_line_ids = fields.One2many(
    'prime.attribution.line',
    'prime_id',
    compute="_compute_employee_lines",
    string="Employés concernés"
)


   
    
    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('prime.attribution')
        record = super().create(vals)
        #record._apply_prime()
        return record
        
    
    def action_confirm(self):
        for rec in self:
            if rec.date_fin < rec.date_debut:
                raise ValidationError("La date de fin doit être supérieure à la date de début.")
            rec.manual_state = 'confirmed'
        
    def action_cancel(self):
        self.manual_state = 'cancelled'

    def action_reset_draft(self):
        self.manual_state = 'draft'
        
    

    

    # =====================
    # AUTO EXPIRATION
    # =====================

    def check_expired(self):
        today = fields.Date.today()
        expired_records = self.search([
            ('state', '=', 'active'),
            ('date_fin', '<', today)
        ])
        expired_records.write({'state': 'expired'})
    
    
    @api.depends('categ_id', 'type_prime')
    def _compute_employee_lines(self):
    
        for rec in self:
            rec.employee_line_ids = [(5, 0, 0)]
    
            if not rec.categ_id:
                continue
    
            employees = self.env['hr.employee'].search([
                ('categ_for_prime', 'in', rec.categ_id.id)
            ])
    
            lines = []
    
            for emp in employees:
                contract = emp.contract_id
                if not contract:
                    continue
    
                values = {
                    'employee_id': emp.id,
                    'contract_id': contract.id,
                    'prime_religieuse': contract.bourse_religieuse,
                    'prime_tech': contract.prime_tech,
                    'trezieme_moi': contract.trezieme_moi,
                }
    
                lines.append((0, 0, values))
    
            rec.employee_line_ids = lines
    
    @api.depends('manual_state', 'date_debut', 'date_fin')
    def _compute_state(self):
        today = fields.Date.today()

        for rec in self:
            if rec.manual_state == 'cancelled':
                rec.state = 'cancelled'

            elif rec.manual_state == 'draft':
                rec.state = 'draft'

            elif rec.manual_state == 'confirmed':
                if rec.date_debut <= today <= rec.date_fin:
                    rec.state = 'active'
                elif today > rec.date_fin:
                    rec.state = 'expired'
                else:
                    rec.state = 'draft'
    
    


class PrimeAttributionLine(models.Model):
    _name = 'prime.attribution.line'
    _description = 'Lignes Employés Prime'

    prime_id = fields.Many2one('prime.attribution')

    employee_id = fields.Many2one('hr.employee')
    contract_id = fields.Many2one('hr.contract')

    prime_religieuse = fields.Float()
    prime_tech = fields.Float()
    trezieme_moi = fields.Float()

