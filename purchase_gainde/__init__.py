from odoo import api, SUPERUSER_ID

from . import models
from . import controllers
from . import wizard

import base64
import os


def post_init_gainde_company(env):
	"""Initialise la société par défaut avec les infos Gainde 2000.

	- Ne s'exécute qu'à l'installation du module.
	- Met à jour uniquement la société par défaut encore générique
	  (nom "My Company" / "Votre société"), pour ne pas écraser
	  une configuration existante.
	"""
	Company = env["res.company"]
	Sequence = env["ir.sequence"].sudo()
	Report = env["ir.actions.report"].sudo()

	company = Company.search([], limit=1)
	if not company:
		return

	# Si la société a déjà été renommée, on considère qu'elle est configurée
	if company.name and company.name not in ("My Company", "Votre société"):
		return

	vals = {}

	# Informations générales
	vals["name"] = "GAINDE 2000"
	if not company.vat:
		vals["vat"] = "SN.DKR.2002.B.1149"
	if not company.website:
		vals["website"] = "http://www.gainde2000.sn"
	if not company.phone:
		vals["phone"] = "(221) 33 859 39 99"
	if not company.mobile:
		vals["mobile"] = "(221) 33 824 17 24"

	# Adresse
	if not company.street:
		vals["street"] = "Point E, Immeuble Orbus Tower"
	if not company.city:
		vals["city"] = "Dakar"
	if not company.country_id:
		country = env["res.country"].search([("code", "=", "SN")], limit=1)
		if country:
			vals["country_id"] = country.id

	# Devise
	if not company.currency_id:
		currency = env["res.currency"].search([("name", "=", "XOF")], limit=1)
		if currency:
			vals["currency_id"] = currency.id

	# Logo : on force le logo Gainde pour la société par défaut
	module_path = os.path.dirname(os.path.realpath(__file__))
	icon_path = os.path.join(module_path, "static", "description", "LOGO_GAINDE.png")
	if os.path.isfile(icon_path):
		with open(icon_path, "rb") as f:
			vals["logo"] = base64.b64encode(f.read())

	if vals:
		company.write(vals)

	# ------------------------------------------------------------------
	# Après l'initialisation de la société, régénérer les Domain Access
	# pour les profils déjà créés (y compris ceux définis en XML à
	# l'installation) en utilisant la logique la plus récente.
	# ------------------------------------------------------------------
	UserManagement = env["user.management"].sudo().with_context(
		install_mode=False,
		gainde_skip_domain_update=False,
	)
	profile_managements = UserManagement.search([("is_profile", "=", True)])
	for management in profile_managements:
		management._gainde_update_domain_access_from_profile_type()

	# ------------------------------------------------------------------
	# Nettoyage: le workflow d'approbation partenaires ne s'applique qu'aux
	# fournisseurs. Si des clients ont été contaminés (démo / anciennes bases),
	# on remet en état brouillon et on supprime route/étapes.
	# ------------------------------------------------------------------
	env["res.partner"]._gainde_cleanup_partner_approval_for_clients()

	# ------------------------------------------------------------------
	# Séquence des commandes d'achat : préfixe BC par défaut
	# ------------------------------------------------------------------
	po_sequences = Sequence.search([("code", "=", "purchase.order")])
	for seq in po_sequences:
		prefix = (seq.prefix or "").strip()
		if prefix.startswith("BC"):
			continue
		if prefix.startswith("PR"):
			seq.write({"prefix": "BC" + prefix[2:]})
		else:
			# Si le préfixe est vide ou différent, forcer BC/
			seq.write({"prefix": "BC/"})

	# ------------------------------------------------------------------
	# Séquence des demandes d'achat : préfixe DA par défaut
	# ------------------------------------------------------------------
	pr_sequences = Sequence.search([("code", "=", "purchase.request")])
	for seq in pr_sequences:
		prefix = (seq.prefix or "").strip()
		if prefix.startswith("DA"):
			continue
		if prefix.startswith("PR"):
			seq.write({"prefix": "DA" + prefix[2:]})
		else:
			seq.write({"prefix": "DA/"})

	# ------------------------------------------------------------------
	# Désactiver les rapports d'impression des commandes d'achat
	# ------------------------------------------------------------------
	report_ids = []
	for xmlid in ("purchase.report_purchaseorder", "purchase.report_purchasequotation"):
		report = env.ref(xmlid, raise_if_not_found=False)
		if report:
			report_ids.append(report.id)
	if report_ids and "active" in Report._fields:
		Report.browse(report_ids).write({"active": False})