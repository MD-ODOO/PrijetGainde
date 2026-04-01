# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AuditGaindeDomain(models.Model):
    _name = 'audit_gainde.domain'
    _description = 'Domaine d\'audit'
    _order = 'name'

    name = fields.Char('Nom domaine', required=True, translate=True)
