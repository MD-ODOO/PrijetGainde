from odoo import models,  fields, api, _


class ResUsers(models.Model):
    _inherit = 'res.users'


    id_signer = fields.Integer("ID Signataire API")
    worker_id = fields.Integer("Worker ID API")
    visual_signature = fields.Binary("Tampon de Signature",
                                     help="Image PNG/JPG de votre signature")

