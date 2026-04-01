# -*- coding: utf-8 -*-

from datetime import date,datetime
from odoo import api, fields, models,_
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError,ValidationError
import logging

_logger = logging.getLogger(__name__)


# =====================================================
# PRIMES
# =====================================================


# =====================================================
# CONTRAT
# =====================================================

class HrContract(models.Model):
    _inherit = 'hr.contract'

    categ_id = fields.Many2one(
        'line.cerco.convention',
        string='Catégorie Employé',
        required=True
    )

    fin_contrat_motif = fields.Selection(
        [
            ('demission', 'Démission'),
            ('licenciement', 'Licenciement'),
            ('faute_lourde', 'Faute lourde'),
        ],
        string="Motif de fin de contrat",
        tracking=True
    )

    fin_contrat_valide = fields.Boolean(
        string="Fin de contrat validée",
        default=False
    )

    date_preavis = fields.Date(
        string="Date de début du préavis"
    )

    duree_preavis = fields.Integer(
        string="Durée du préavis (jours)",
        compute="_compute_duree_preavis",
        store=True
    )

    indemite_preavis = fields.Float(
        string="Indemnité de préavis",
        compute="_compute_indemnite_preavis",
        store=True
    )

    is_cdi = fields.Boolean(
        compute="_compute_is_cdi",
        store=True
    )

    show_preavis = fields.Boolean(
        compute="_compute_show_preavis",
        store=True
    )

    contrat_termine = fields.Boolean(
        compute="_compute_contrat_termine",
        store=True
    )
    
    show_fin_contrat = fields.Boolean(
    compute="_compute_show_fin_contrat",
    store=True
    )

    # ======================
    # COMPUTES
    # ======================

    @api.depends('contract_type_id.code')
    def _compute_is_cdi(self):
        for rec in self:
            rec.is_cdi = rec.contract_type_id.code == 'cdi'

    @api.depends('date_end', 'date_preavis')
    def _compute_duree_preavis(self):
        for rec in self:
            if rec.date_end and rec.date_preavis:
                rec.duree_preavis = (rec.date_end - rec.date_preavis).days
            else:
                rec.duree_preavis = 0

    @api.depends('duree_preavis', 'wage')
    def _compute_indemnite_preavis(self):
        for rec in self:
            if rec.duree_preavis > 0 and rec.wage:
                rec.indemite_preavis = (rec.wage / 30) * rec.duree_preavis
            else:
                rec.indemite_preavis = 0.0

    @api.depends('contract_type_id.code', 'fin_contrat_motif')
    def _compute_show_preavis(self):
        for rec in self:
            if rec.contract_type_id.code != 'cdi':
                rec.show_preavis = True
            elif rec.fin_contrat_motif in ['licenciement','demission']:
                rec.show_preavis = True
            else:
                rec.show_preavis = False

    @api.depends('state')
    def _compute_contrat_termine(self):
        for rec in self:
            rec.contrat_termine = rec.state == 'close'

    # ======================
    # ONCHANGE
    # ======================

    @api.onchange('contract_type_id')
    def _onchange_contract_type_id(self):
        for rec in self:
            if rec.contract_type_id.code == 'cdi':
                rec.date_preavis = False
                rec.duree_preavis = 0
                rec.indemite_preavis = 0.0

    # ======================
    # CONTRAINTES
    # ======================

    @api.constrains('date_preavis', 'date_end')
    def _check_dates_preavis(self):
        for rec in self:
            if rec.date_preavis and rec.date_end:
                if rec.date_preavis > rec.date_end:
                    raise ValidationError(
                        _("La date de début du préavis ne peut pas être postérieure "
                          "à la date de fin du contrat.")
                    )

    # ======================
    # WORKFLOW NATIF
    # ======================

    def action_valider_fin_contrat(self):
        for rec in self:
            if not rec.fin_contrat_motif:
                raise ValidationError(
                    _("Veuillez renseigner le motif de fin de contrat.")
                )
            if not rec.date_end:
                raise ValidationError(
                    _("Veuillez renseigner la date de fin du contrat.")
                )
            rec.fin_contrat_valide = True

    
        
    @api.onchange('state')
    def _onchange_state_reset_fin_contrat(self):
        for rec in self:
            if rec.state != 'close':
                rec.fin_contrat_motif = False
                rec.date_end = False
                rec.date_preavis = False
                rec.duree_preavis = 0
                rec.indemite_preavis = 0.0
    
    @api.depends('state')
    def _compute_show_fin_contrat(self):
        for rec in self:
            rec.show_fin_contrat = rec.state == 'close'
    
    def write(self, vals):
        for rec in self:
            if vals.get('state') == 'close':
                if not rec.fin_contrat_motif:
                    raise ValidationError(
                        _("Le motif de fin de contrat est obligatoire.")
                    )
                if not rec.date_end:
                    raise ValidationError(
                        _("La date de fin du contrat est obligatoire.")
                    )
        return super().write(vals)
                        
                
    indemite_preavis = fields.Float(string="Indemnite preavis", compute="_compute_indemnite_preavis")

    # Salaire & primes principales
    salaire_net = fields.Float('Salaire Net')
    trezieme_moi = fields.Float('Treizième Mois',compute="_compute_primes",
        store=False)
    ret_nsia = fields.Float('Retenue NSIA')
    ret_pretpersonnel = fields.Float('Retenue Prêt Personnel')
    ret_cotretraite = fields.Float('Retenue Epargne Retraite')
    ret_parcking = fields.Float('Retenue Prarcking')
    ret_pretvehicul = fields.Float('Retenue Prêt Véhicule')
    ret_pretEquipement = fields.Float('Retenue Prêt Equipement')
    ret_pretordinaire = fields.Float('Retenue Prêt Ordinaire')
    ret_pretcooperative = fields.Float('Retenue Prêt Coopérative')
    ret_assarvie = fields.Float('Retenue Assurance SAAR Vie')
    ret_frais_medicaux = fields.Float('Retenue Frais Médicaux ')
    ret_avance_sursalaire = fields.Float('Retenue Avance sur Salaire ')
    ret_avance_surprime = fields.Float('Retenue Avance sur Prime ')
    ret_avance_14mois = fields.Float('Retenue Avance sur 14ème Mois')
    ret_epargne_illico = fields.Float('Retenue Epargne IILICO')
    
    prime_astreinte = fields.Float('Prime Astreinte')
    prime_exceptionnele = fields.Float('Prime Exceptionnel')
    prime_perfom = fields.Float('Prime de Performance')
    prime_tech = fields.Float('Primee Technique',compute="_compute_primes",
        store=False )
    prime_Special = fields.Float('Prime Spéciale')
    prime_technicity = fields.Float('Prime de Technicité')
    prime_bourse_religieux = fields.Float('Prime Religieux')
    sursalaire = fields.Float(string="Sursalaire")
    carburant = fields.Float(string="Carburant")
    carburant_non_imposable = fields.Float(string="Carburant non imposable")
    remboursement = fields.Float(string="Remboursement frais de formation")
    rapel_salaire = fields.Float(string="Rappel de Salaire")
    avantage_nature = fields.Float(string="Avantage en Nature")
    prime_anciennete = fields.Float(string="Prime de Fidélité ")
    bourse_religieuse = fields.Float(string="Bourse Religieuse ",compute="_compute_primes",
        store=False)
    prime_iso = fields.Float(string="Prime ISO ",compute="_compute_primes",
        store=False)

    prime_caisse = fields.Float(string="Prime de Caisse")
    avance_tabaski = fields.Float(string="Avance tabaski")
    avance_korite = fields.Float(string="Avance Korite")
    avance_noel = fields.Float(string="Avance Noel")

    
    indemite_compensation_preavis = fields.Float(string="Compensation preavis")
    indemite_kilometrique = fields.Float(string="Indemnite Kilometrique")
    indemnite_conges = fields.Float(string="Congés payés non imposable")

    retenu_sport = fields.Float(string="Retenue de sport")
    retenu = fields.Float(string="Retenue pret")
    retenue_car = fields.Float(string="Retenue Car Plan")
    retenu_sante = fields.Float(string="Retenue assurance maladie")
    retenu_avance_conge = fields.Float(string="Retenue avance sur Congés")

    prime_exc = fields.Float(string="Prime Exceptionnelle")
    prime_rendement = fields.Float(string="Prime de Rendement")
    prime_resp = fields.Float(string="Prime de responsabilite")
    prime_risque = fields.Float(string="Prime de Risque")
    prime_salissure = fields.Float(string="Prime de salissure")
    prime_transport = fields.Float(string="Indemnité de transport",default="26000")

    nb_days = fields.Integer(string="Anciennete")
    cumul_jour = fields.Float("Cumul jours anterieur")
    cumul_conges = fields.Float("Cumul indemnite de conges anterieurs")
    nbj_alloue = fields.Float("Nombre de jours alloues", default="2.5")
    nbj_travail = fields.Float("Nombre de jours de travail", default="30")
    nbj_aquis = fields.Float("Nombre de jours acquis", store=True)
    convention_id = fields.Many2one('line.cerco.convention','Catégorie')
    nbj_pris = fields.Float("Nombre de jours pris", default="0")
    cumul_mesuel = fields.Float("Cumul mensuel conges")
    last_date = fields.Date("derniere date")
    alloc_conges = fields.Float("Allocation conges", compute="_compute_alloc_conges")




    year_extra_day_anciennete = fields.Integer()
    # nbj_sup = fields.Float("Nombre de jour supplementaire", related="employee_id.nbj_sup")
    restauration = fields.Float(string="Restauration")
    ticket_restau = fields.Float(string="Ticket restaurant")
    prime_logement = fields.Float(string="Prime de logement")
    remboursement_formation = fields.Float(string="remboursement formation")

    #New ajout  ####
    regul_salaire = fields.Float(string='Régularisation salaire de base')
    over_salaire_base = fields.Float(string='Trop perçu salaire de base')
    regul_sursalaire = fields.Float(string='Régularisation sursalaire')
    regul_moins_percu_prime_respon = fields.Float(string='Régul moins perçu prime de respon')
    regul_prime_respon = fields.Float(string='Régul prime de responsabilité')
    or_regul_prime_log = fields.Float(string='Or prime de logement')
    regul_prime_log = fields.Float(string='Regul prime de logement')
    over_prime_resp = fields.Float(string='Trop perçu prime de respon')
    over_prime_indemn = fields.Float(string='Trop perçu prime et indemnité')
    prime_pacer = fields.Float(string='Prime de coordonation PACER')
    prime_sujetion = fields.Float(string='Prime de sujétion')
    regul_prime_sujetion = fields.Float(string='Régul Indemnité de sujétion')
    remb_prime_interim = fields.Float(string="Remb. prime d'intérim")
    regul_prime_interim = fields.Float(string="Régul. prime d'intérim")
    prime_pme_pmi = fields.Float(string="Prime de coordination PME/PMI")
    indem_fonction = fields.Float(string="Indemnité de fonction")
    prim_resp = fields.Float(string="Prime de responsabilité")
    over_prim_resp = fields.Float(string="Trop perçu Prime de respons")
    prim_tresorerie = fields.Float(string="Prime de trésorerie")
    prim_recouvrement = fields.Float(string="Prime de recouvrement")
    prim_respon_chauffeur = fields.Float(string="Prime de responsab chauff DG")
    forfait_heure_sup = fields.Float(string="Forfait heures Sup")
    regul_forfait_heure_sup = fields.Float(string="Régul Forfait heures Sup")
    prime_caisse = fields.Float(string="Prime de caisse")
    prime_facturation = fields.Float(string="Prime de facturation")
    indemn_tel = fields.Float(string="Indemnité Téléphone")
    indemn_eau_elect = fields.Float(string="Indemnité Eau et Elect")
    frais_representation = fields.Float(string="Frais de représentation")
    indmn_logement = fields.Float(string="Indemnité de logement")
    over_indmn_logement = fields.Float(string="Trop perçu Indemn de loge")
    compl_remun = fields.Float(string="Complément de rémunération")
    crrae_rcpne = fields.Float(string="Base CRRAE RCPNE")
    allocation_familiale = fields.Float(string='Allocation familiale')
    frais_medical = fields.Float(string='Ordre de Frais médicaux')
    conges_payes = fields.Float(string='Congés payés')


    retenu_amical = fields.Float(string="Retenue amicale")
    retenu_rvc = fields.Float(string='Retenue RVC CRRAE UEMOA')
    
    contract_date_end = fields.Date(string="Date de retraite", compute='_compute_contract_date_end', store=True)
    post_duration = fields.Char(string="Ancienneté", compute='_compute_post_duration')
    regime_type = fields.Selection([('cadre', 'CADRE'), ('non_cadre', 'NON CADRE'),('cs','Cadre Supérieur'),('cm','Cadre Moyen')], string='Statut')




    @api.depends('date_start')
    def _compute_post_duration(self):
        today = date.today()
        for emp in self:
            if emp.date_start:
                d = relativedelta(today, emp.date_start)
                emp.post_duration = f"{d.years} an(s) - {d.months} mois - {d.days} jours"
            else:
                emp.post_duration = ""

    
    @api.depends('employee_id.birthday')
    def _compute_contract_date_end(self):
        for emp in self:
            emp.contract_date_end = emp.employee_id.birthday + relativedelta(years=60) if emp.employee_id.birthday else False

    @api.onchange("categ_id")
    def onchange_categ(self):
        if self.categ_id:
            self.wage = self.categ_id.wage
            
    
    @api.depends('employee_id', 'employee_id.categ_for_prime')
    def _compute_primes(self):
    
        today = fields.Date.today()
    
        primes = self.env['prime.attribution'].search([
            ('manual_state', '=', 'confirmed'),
            ('date_debut', '<=', today),
            ('date_fin', '>=', today)
        ])
    
    
        primes_by_categ = {}
        for prime in primes:
            primes_by_categ.setdefault(prime.categ_id.id, []).append(prime)
    
        for contract in self:
            relig_total = 0.0
            tech_total = 0.0
            treizieme_total = 0.0
            prime_iso=0.0
    
            categories = contract.employee_id.categ_for_prime
    
            for categ in categories:
                for prime in primes_by_categ.get(categ.id, []):
                    if prime.type_prime == 'religieuse':
                        relig_total += prime.valeur_prime
    
                    elif prime.type_prime == '13eme':
                        treizieme_total += prime.valeur_prime
    
                    elif prime.type_prime == 'tech':
                        tech_total += prime.valeur_prime
                    
                    elif prime.type_prime == 'iso':
                        prime_iso += prime.valeur_prime
                    
                    

            contract.bourse_religieuse = relig_total
            contract.prime_tech = tech_total
            contract.trezieme_moi = treizieme_total
            contract.prime_iso = prime_iso   
            
            


    # -------------------------------------------------
    # ONCHANGE JOB / EMPLOYEE
    # -------------------------------------------------

    # @api.onchange('job_id', 'employee_id')
    # def set_primes(self):
    #     for contract in self:
    #         if contract.employee_id:
    #             contract.categ_id = contract.employee_id.categ_id
    #             contract.function_id = contract.employee_id.function_id
    #             contract.date_start = contract.employee_id.contract_date_start

    #         # Règles par régime
    #         regime_rules = {
    #             'cs': {'indmn_logement': 125000, 'prime_transport': 50000, 'forfait_heure_sup': 20000},
    #             'cm': {'indmn_logement': 75000, 'prime_transport': 35000, 'forfait_heure_sup': 15000},
    #             'non_cadre': {'indmn_logement': 60000, 'prime_transport': 25000, 'forfait_heure_sup': 15000},
    #         }

    #         if contract.employee_id and contract.employee_id.regime_type in regime_rules:
    #             for field, value in regime_rules[contract.employee_id.regime_type].items():
    #                 setattr(contract, field, value)
    #             continue

    #         # Règles par code poste
    #         if contract.job_id and contract.job_id.code:
    #             job_rules = {
    #                 1: {'indmn_logement': 190000, 'prime_transport': 100000, 'forfait_heure_sup': 25000},
    #                 2: {'indmn_logement': 175000, 'prime_transport': 80000,  'forfait_heure_sup': 25000},
    #                 3: {'indmn_logement': 150000, 'prime_transport': 80000,  'forfait_heure_sup': 20000},
    #             }

    #             rules = job_rules.get(contract.job_id.code)
    #             if rules:
    #                 for field, value in rules.items():
    #                     setattr(contract, field, value)


    # -------------------------------------------------
    # CONGÉS
    # -------------------------------------------------

   


    def _compute_extra_day_seniority(self, date_payslip, nb_days):
        try:
            date_payslip = datetime.strptime(date_payslip, '%Y-%m-%d')
        except Exception:
            raise UserError(_("Date invalide"))

        for rec in self:
            if rec.year_extra_day_anciennete != date_payslip.year:
                rec.year_extra_day_anciennete = date_payslip.year
                rec.nbj_aquis += nb_days



#
