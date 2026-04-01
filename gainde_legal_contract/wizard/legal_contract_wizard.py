import base64
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class LegalContractGenerateWizard(models.TransientModel):
    _name = 'legal.contract.generate.wizard'
    _description = 'Générer Contrat PDF'

    contract_id = fields.Many2one('legal.contract', required=True)
    template_id = fields.Many2one('ir.actions.report', string="Modèle PDF")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id') or self.env.context.get(
            'default_contract_id')
        if active_id:
            contract = self.env['legal.contract'].browse(active_id)
            res['contract_id'] = active_id
            if contract.type_id and hasattr(contract.type_id,
                                            'template_id') and contract.type_id.template_id:
                res['template_id'] = contract.type_id.template_id.id
        return res

    def action_generate_pdf(self):
        self.ensure_one()
        contract = self.contract_id

        # 1. Calcul du nom de version (Inchangé)
        version_count = self.env['ir.attachment'].sudo().search_count([
            ('res_model', '=', 'legal.contract'),
            ('res_id', '=', contract.id),
            ('name', 'like', 'Contrat_%')
        ])
        filename = f"Contrat_{contract.name}_v{version_count + 1}.pdf"

        # 2. Génération du PDF
        report_action = contract.type_id.template_id
        pdf_content, _ = report_action.sudo()._render_qweb_pdf(
            report_action.report_name, res_ids=contract.ids
        )

        # 3. CRÉATION DE L'ATTACHMENT
        # Odoo 18 va créer AUTOMATIQUEMENT un documents.document ici
        attachment = self.env['ir.attachment'].sudo().create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'mimetype': 'application/pdf',
            'res_model': 'legal.contract',
            'res_id': contract.id,
        })

        # 4. RÉCUPÉRATION DU DOCUMENT AUTO-GÉNÉRÉ PAR ODOO
        # On ne fait pas de .create(), on cherche celui qui existe déjà
        new_doc = self.env['documents.document'].sudo().search([
            ('attachment_id', '=', attachment.id)
        ], limit=1)

        if new_doc:
            # On applique logique de hiérarchie sur le document existant
            user_dept = self.env.user.department_id
            target_folder = new_doc._get_hierarchy_folder(user_dept)

            new_doc.write({
                'folder_id': target_folder.id,
                'department_id': user_dept.id if user_dept else False,
            })

            # Liaison au champ Many2many du contrat
            contract.write({'document_ids': [(4, attachment.id)]})
        else:
            # Fallback : Si Odoo n'a rien créé (rare), on utilise votre méthode
            self.env['documents.document'].sudo().classify_attachment(
                attachment.id, 'legal.contract', contract.id
            )

        # 5. TÉLÉCHARGEMENT
        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/{attachment.id}?download=true",
            'target': 'self',
        }



