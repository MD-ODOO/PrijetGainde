from odoo import api, fields, models, _
from odoo.tools import html_escape


class OrbusFactureBatch(models.Model):
    _name = "orbus.facture.batch"
    _description = "Lot de factures Orbus par periode"
    _order = "request_date desc, id desc"

    name = fields.Char(
        string="Libelle",
        required=True,
        default=lambda self: _("Batch factures Orbus"),
    )

    code = fields.Char(
        string="Reference batch",
        required=True,
        help="Code de reference base sur la periode et les parametres utilises.",
    )

    periode = fields.Char(
        string="Periode",
        required=True,
        help="Periode Orbus au format AAAA-MM (ex: 2017-09).",
    )

    params_json = fields.Text(
        string="Parametres bruts",
        help="Parametres utilises pour appeler l'API GetFacturesByPeriode.",
    )

    status_code = fields.Char(string="Code statut")
    status = fields.Char(string="Statut")
    message = fields.Char(string="Message")

    request_date = fields.Datetime(
        string="Date de recuperation",
        default=lambda self: fields.Datetime.now(),
    )

    company_id = fields.Many2one(
        "res.company",
        string="Societe",
        required=True,
        default=lambda self: self.env.company,
    )

    line_ids = fields.One2many(
        "orbus.facture.batch.line",
        "batch_id",
        string="Factures",
    )

    api_summary_html = fields.Html(
        string="Synthèse API",
        compute="_compute_api_summary_html",
        store=True,
    )

    def _build_summary_html(self, errors, result_text):
        if errors:
            items = "".join(
                "<li><strong>%s</strong> : %s</li>" % (
                    html_escape(label),
                    html_escape(msg),
                )
                for label, msg in errors
            )
            return (
                "<div>"
                "<span class='badge badge-danger'>Erreurs</span>"
                "<ul>"
                + items
                + "</ul>"
                "</div>"
            )

        result_text = result_text or "Aucune erreur détectée."
        return (
            "<div>"
            "<span class='badge badge-success'>OK</span>"
            "<div>"
            + html_escape(result_text)
            + "</div>"
            "</div>"
        )

    @api.depends(
        "line_ids.state",
        "line_ids.error_message",
        "line_ids.numero_facture",
        "message",
        "status",
        "status_code",
    )
    def _compute_api_summary_html(self):
        for batch in self:
            errors = []
            for line in batch.line_ids:
                if line.state == "error":
                    label = line.numero_facture or "Ligne %s" % line.id
                    msg = line.error_message or "Erreur inconnue"
                    errors.append((label, msg))

            result_parts = []
            if batch.message:
                result_parts.append(batch.message)
            if batch.status_code:
                result_parts.append("Code %s" % batch.status_code)
            if batch.status:
                result_parts.append(batch.status)

            result_text = " - ".join(result_parts)
            batch.api_summary_html = batch._build_summary_html(errors, result_text)

    def action_create_invoices(self):
        """Cree en masse les factures Odoo pour les lignes non facturees.

        - ne traite que les lignes sans invoice_id
        - utilise orbus.api.config.create_odoo_invoice_from_orbus_facture
        - met a jour l'etat de chaque ligne (state)
        - commit regulier pour eviter les timeouts
        """
        for batch in self:
            config = self.env["orbus.api.config"].get_config_for_company(batch.company_id)
            pending_lines = batch.line_ids.filtered(lambda l: not l.invoice_id)
            
            total = len(pending_lines)
            for idx, line in enumerate(pending_lines, 1):
                if not line.numero_facture:
                    line.state = "error"
                    line.error_message = "Numero de facture Orbus manquant."
                    continue
                try:
                    invoice = config.create_odoo_invoice_from_orbus_facture(line.numero_facture)
                except Exception as e:  # pragma: no cover
                    line.state = "error"
                    line.error_message = str(e)
                    continue

                line.invoice_id = invoice.id
                line.state = "invoiced"
                line.error_message = False
                
                # Commit tous les 10 enregistrements pour eviter timeout
                if idx % 10 == 0:
                    self.env.cr.commit()
            
            # Commit final
            self.env.cr.commit()

    def action_delete_lines(self):
        """Supprime toutes les lignes du batch."""
        for batch in self:
            batch.line_ids.unlink()
        return True


class OrbusFactureBatchLine(models.Model):
    _name = "orbus.facture.batch.line"
    _description = "Facture Orbus dans un lot"
    _order = "id desc"

    batch_id = fields.Many2one(
        "orbus.facture.batch",
        string="Lot",
        required=True,
        ondelete="cascade",
    )

    numero_facture = fields.Char(string="Numero facture")
    numero_client = fields.Char(string="Numero client")
    nom_client = fields.Char(string="Nom client")

    montant_ttc = fields.Float(string="Montant TTC")
    montant_tva = fields.Float(string="Montant TVA")
    montant_ht = fields.Float(
        string="Montant taxable (HT)",
        help="Montant HT taxable calculé à partir des règles Orbus.",
    )
    montant_du = fields.Float(
        string="Montant dû",
        help="Montant restant dû (si non fourni, égal au TTC).",
    )
    devise = fields.Char(string="Devise")

    montant_taxe_18 = fields.Float(
        string="Taxe 18%",
        help="Montant de la taxe calculee a 18% du montant TTC.",
    )

    montant_taxable = fields.Float(
        string="Montant taxable",
        help="Partie de la base soumise a la TVA (HT taxable).",
    )

    montant_non_taxable = fields.Float(
        string="Montant non taxable",
        help="Partie de la base exoneree de TVA selon les regles Orbus.",
    )

    invoice_id = fields.Many2one(
        "account.move",
        string="Facture Odoo",
        readonly=True,
    )

    state = fields.Selection(
        [
            ("pending", "En attente"),
            ("invoiced", "Facture creee"),
            ("error", "Erreur"),
        ],
        string="Etat facture",
        default="pending",
        readonly=False,
    )

    error_message = fields.Char(string="Message d'erreur")

    company_id = fields.Many2one(
        related="batch_id.company_id",
        store=True,
        readonly=True,
    )
