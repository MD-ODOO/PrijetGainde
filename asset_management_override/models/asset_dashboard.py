from odoo import models, fields, api


class AssetDashboard(models.Model):
    _name = 'asset.dashboard'
    _description = 'Dashboard pour la gestion des actifs'
    _auto = False  # Vue SQL, pas de table physique

    status = fields.Selection([
        ('draft', 'Brouillon'),
        ('assign', 'Affecté'),
        ('return', 'Retour'),
        ('on_hold', 'En attente'),
        ('in_warehouse', 'Disponible'),
        ('repair', 'Maintenance'),
        ('destroyed', 'Sortie'),
    ], string='Statut')

    localisation_id = fields.Many2one('asset.localisation', string='Localisation')
    localisation_name = fields.Char(string='Site')
    asset_count = fields.Integer(string="Nombre d'actifs")
    total_amount = fields.Float(string='Valeur totale')

    def init(self):
        self.env.cr.execute("DROP VIEW IF EXISTS asset_dashboard")
        self.env.cr.execute("""
            CREATE VIEW asset_dashboard AS (
                SELECT
                    ROW_NUMBER() OVER () as id,
                    am.status,
                    am.localisation as localisation_id,
                    COALESCE(al.name, 'Sans localisation') as localisation_name,
                    COUNT(*) as asset_count,
                    SUM(COALESCE(aa.book_value, 0)) as total_amount
                FROM asset_management am
                LEFT JOIN asset_localisation al ON am.localisation = al.id
                LEFT JOIN account_asset aa ON am.account_asset_id = aa.id
                GROUP BY am.status, am.localisation, al.name
            )
        """)

    @api.model
    def get_dashboard_data(self):
        # Toujours basé sur l'état actuel du parc (pas de filtre par date d'acquisition)
        # Les actifs ont une longue durée de vie — c'est le statut/cycle de vie qui compte

        # Global — actifs non sortis
        assets = self.env['asset.management'].search([('status', '!=', 'destroyed')])
        total_assets = len(assets)
        total_value = sum(assets.mapped('book_value'))

        # Répartition par statut (tous statuts, y compris Sorti pour info)
        statuses = [
            ('draft',        'Brouillon'),
            ('assign',       'Affecté'),
            ('in_warehouse', 'Disponible'),
            ('repair',       'Maintenance'),
            ('return',       'Retour'),
            ('on_hold',      'En attente'),
            ('destroyed',    'Sortie'),
        ]
        status_data = []
        for status_code, status_label in statuses:
            grp = self.env['asset.management'].search([('status', '=', status_code)])
            if grp:
                status_data.append({
                    'status': status_code,
                    'label': status_label,
                    'count': len(grp),
                    'value': sum(grp.mapped('book_value')),
                })

        # Répartition par localisation — actifs non sortis
        self.env.cr.execute("""
            SELECT
                COALESCE(al.name, 'Sans localisation') as location_name,
                COUNT(am.id) as asset_count,
                SUM(COALESCE(aa.book_value, 0)) as total_amount,
                al.id as localisation_id
            FROM asset_management am
            LEFT JOIN asset_localisation al ON am.localisation = al.id
            LEFT JOIN account_asset aa ON am.account_asset_id = aa.id
            WHERE am.status != 'destroyed'
            GROUP BY al.id, al.name
            ORDER BY total_amount DESC
        """)

        location_data = [
            {'location': row[0], 'count': row[1], 'value': float(row[2]), 'localisation_id': row[3] or 0}
            for row in self.env.cr.fetchall()
        ]

        # Currency info
        currency = self.env.company.currency_id
        return {
            'total_assets': total_assets,
            'total_value': total_value,
            'status_data': status_data,
            'location_data': location_data,
            'currency_symbol': currency.symbol or 'FCFA',
            'currency_position': currency.position or 'after',
        }
