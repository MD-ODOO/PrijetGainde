from odoo import models, fields, api, _
from datetime import datetime


class DocumentsDocument(models.Model):
    _name = 'documents.document'
    _inherit = ['documents.document', 'abstract.signable.document']

    department_id = fields.Many2one(
        'hr.department',
        string="Département",
        help="Définit la visibilité du dossier/document par département"
    )

    @api.model
    def classify_attachment(self, attachment_id, res_model, res_id):
        """
        Crée un enregistrement documents.document wrappant l'ir.attachment
        et le place dans le bon dossier automatique.
        """

        attachment = self.env['ir.attachment'].browse(attachment_id)
        source_record = self.env[res_model].browse(res_id)

        # Extraction du département d'origine du DOCUMENT
        dept = False
        if 'department_id' in source_record._fields:
            dept = source_record.department_id
        elif ('employee_id' in source_record._fields and
              source_record.employee_id.department_id):
            dept = source_record.employee_id.department_id

        # Fallback sur le département de l'utilisateur si non trouvé sur le doc
        if not dept:
            dept = self.env.user.department_id

        target_folder = self._get_hierarchy_folder(dept)

        return self.create({
            'name': attachment.name,
            'folder_id': target_folder.id,
            'attachment_id': attachment.id,
            'type': 'binary',
            'res_model': res_model,
            'res_id': res_id,
            'department_id': dept.id if dept else False,
        })

    def _get_hierarchy_folder(self, dept):
        """
        Crée récursivement GED GAINDE > DEPT > ANNÉE > MOIS
        Force l'utilisation de la racine "GED GAINDE"
        """
        root = self._get_or_create_f("GED GAINDE")
        if not dept: return root

        d_folder = self._get_or_create_f(dept.name, root.id, dept.id)
        y_folder = self._get_or_create_f(str(datetime.now().year),
                                         d_folder.id, dept.id)
        m_folder = self._get_or_create_f(
            datetime.now().strftime("%m - %B"), y_folder.id, dept.id)
        return m_folder

    def _get_or_create_f(self, name, parent_id=False, dept_id=False):
        """ Crée ou retrouve un dossier et applique les droits """

        folder = self.search([('name', '=', name), ('type', '=', 'folder'),
                         ('folder_id', '=', parent_id)], limit=1)
        if not folder:
            folder = self.create({'name': name, 'type': 'folder', 'folder_id': parent_id,
                             'department_id': dept_id})
        return folder

