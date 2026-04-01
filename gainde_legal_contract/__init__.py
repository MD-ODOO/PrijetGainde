from . import models
from . import wizard

from odoo import api, SUPERUSER_ID

def _uninstall_cleanup_ged(env):
    """ Supprime les dossiers GED créés par le module même s'ils sont en noupdate=1 """
    # On récupère les IDs externes des dossiers
    xml_ids = [
        'folder_ged_root',
        'folder_contrats',
        'folder_factures',
        'folder_paie',
        'folder_rh'
    ]
    for xml_id in xml_ids:
        # On cherche l'enregistrement lié à l'ID externe du module
        record = env.ref(f'gainde_legal_contract.{xml_id}', raise_if_not_found=False)
        if record:
            record.unlink()

