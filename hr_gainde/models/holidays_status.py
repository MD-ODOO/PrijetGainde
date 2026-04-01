# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import math


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    number_legal_days_per_year = fields.Integer(
        string="Nombre de jours autorisés"
    )

    is_not_deductible = fields.Boolean(
        string="Congés non déductibles"
    )

    is_legal_leave = fields.Boolean(
        string="Congés payés"
    )

    # ==================================================
    # DISPLAY NAME (ex-name_get)
    # ==================================================
    def name_get(self):
        result = []
        employee = self.env.context.get('employee_id')

        if not employee:
            return super().name_get()

        employee = self.env['hr.employee'].browse(employee)

        for leave_type in self:
            name = leave_type.name

            # Si allocation requise
            if leave_type.requires_allocation:
                allocation = self.env['hr.leave.allocation'].search([
                    ('employee_id', '=', employee.id),
                    ('holiday_status_id', '=', leave_type.id),
                    ('state', '=', 'validate')
                ], limit=1)

                remaining = allocation.remaining_leaves if allocation else 0.0
                total = allocation.number_of_days if allocation else 0.0

                name = f"{name} ({math.floor(remaining)} restant sur {math.floor(total)})"

            result.append((leave_type.id, name))

        return result
