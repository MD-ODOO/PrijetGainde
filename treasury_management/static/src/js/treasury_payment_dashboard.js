/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

// ─── Helpers date ────────────────────────────────────────────────────────────

function isoDate(d) {
    return d.toISOString().slice(0, 10);
}

function addMonths(d, n) {
    const r = new Date(d);
    r.setMonth(r.getMonth() + n);
    return r;
}

function monthStart(d) {
    return new Date(d.getFullYear(), d.getMonth(), 1);
}

function monthEnd(d) {
    return new Date(d.getFullYear(), d.getMonth() + 1, 0);
}

function defaultPeriod(preset) {
    const today = new Date();
    switch (preset) {
        case "current_month":
            return { date_from: isoDate(monthStart(today)), date_to: isoDate(monthEnd(today)) };
        case "next_month": {
            const nm = addMonths(today, 1);
            return { date_from: isoDate(monthStart(nm)), date_to: isoDate(monthEnd(nm)) };
        }
        case "current_quarter": {
            const q = Math.floor(today.getMonth() / 3);
            const qs = new Date(today.getFullYear(), q * 3, 1);
            const qe = new Date(today.getFullYear(), q * 3 + 3, 0);
            return { date_from: isoDate(qs), date_to: isoDate(qe) };
        }
        case "next_3_months":
        default: {
            const end = addMonths(monthEnd(today), 2);
            return { date_from: isoDate(monthStart(today)), date_to: isoDate(monthEnd(end)) };
        }
    }
}

// ─── Component ───────────────────────────────────────────────────────────────

export class TreasuryPaymentDashboard extends Component {
    static template = "treasury_management.TreasuryPaymentDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        const initPeriod = defaultPeriod("next_3_months");
        this.state = useState({
            data: null,
            loading: true,
            activeTab: "urgent",
            // Forecast state
            forecastPreset: "next_3_months",
            forecastDateFrom: initPeriod.date_from,
            forecastDateTo: initPeriod.date_to,
            forecast: null,
            forecastLoading: false,
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    // ─── Data loading ─────────────────────────────────────────────────────────

    async loadData() {
        this.state.loading = true;
        try {
            const [data] = await Promise.all([
                this.orm.call("treasury.payment", "get_payment_dashboard_data", [], {}),
            ]);
            this.state.data = data;
        } catch (error) {
            console.error(error);
            this.state.data = this._fallbackData();
            this.notification.add(_t("Impossible de charger les données du tableau de bord."), { type: "warning" });
        } finally {
            this.state.loading = false;
        }
        // Load forecast in parallel without blocking main render
        await this.loadForecast();
    }

    async loadForecast() {
        this.state.forecastLoading = true;
        try {
            this.state.forecast = await this.orm.call(
                "treasury.payment",
                "get_treasury_forecast",
                [],
                { date_from: this.state.forecastDateFrom, date_to: this.state.forecastDateTo }
            );
        } catch (error) {
            console.error(error);
            this.state.forecast = null;
        } finally {
            this.state.forecastLoading = false;
        }
    }

    async refresh() {
        await this.loadData();
    }

    // ─── Forecast controls ────────────────────────────────────────────────────

    async onForecastPresetChange(ev) {
        const preset = ev.target.value;
        this.state.forecastPreset = preset;
        if (preset !== "custom") {
            const p = defaultPeriod(preset);
            this.state.forecastDateFrom = p.date_from;
            this.state.forecastDateTo = p.date_to;
            await this.loadForecast();
        }
    }

    async onForecastDateChange() {
        this.state.forecastPreset = "custom";
        if (this.state.forecastDateFrom && this.state.forecastDateTo) {
            await this.loadForecast();
        }
    }

    // ─── Navigation ───────────────────────────────────────────────────────────

    setTab(tab) {
        this.state.activeTab = tab;
    }

    async openRecord(id) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "treasury.payment",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async openList(domain, name) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: name,
            res_model: "treasury.payment",
            views: [[false, "list"], [false, "form"]],
            domain: domain,
            target: "current",
        });
    }

    openPending() {
        this.openList([["state", "not in", ["paid", "cancelled"]]], "Paiements en instance");
    }
    openUrgent() {
        this.openList(
            [["state", "not in", ["paid", "cancelled"]], ["priority", "in", ["2", "3"]]],
            "Paiements urgents"
        );
    }
    openOverdue() {
        const today = isoDate(new Date());
        this.openList(
            [["state", "not in", ["paid", "cancelled"]], ["planned_payment_date", "<", today]],
            "Paiements en retard"
        );
    }
    openUpcoming() {
        const today = isoDate(new Date());
        const in7 = isoDate(new Date(Date.now() + 7 * 86400000));
        this.openList(
            [
                ["state", "not in", ["paid", "cancelled"]],
                ["planned_payment_date", ">=", today],
                ["planned_payment_date", "<=", in7],
            ],
            "Paiements à venir (7 jours)"
        );
    }

    openForecastPayments(month) {
        this.openList(
            [
                ["state", "not in", ["paid", "cancelled"]],
                ["planned_payment_date", ">=", month.date_from],
                ["planned_payment_date", "<=", month.date_to],
            ],
            `Décaissements — ${month.label}`
        );
    }

    openForecastReceipts(month) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: `Encaissements — ${month.label}`,
            res_model: "treasury.receipt",
            views: [[false, "list"], [false, "form"]],
            domain: [
                ["state", "not in", ["paid", "cancelled"]],
                ["planned_receipt_date", ">=", month.date_from],
                ["planned_receipt_date", "<=", month.date_to],
            ],
            target: "current",
        });
    }

    // ─── Formatting ───────────────────────────────────────────────────────────

    formatCurrency(amount, company) {
        const c = company || (this.state.data && this.state.data.company);
        const symbol = (c && c.currency_symbol) || "";
        const pos = (c && c.currency_position) || "after";
        const value = (amount || 0).toLocaleString("fr-FR", { maximumFractionDigits: 0 });
        return pos === "after" ? `${value} ${symbol}` : `${symbol} ${value}`;
    }

    formatJournalBalance(amount, journal) {
        const symbol = journal.currency_symbol || "";
        const pos = journal.currency_position || "after";
        const value = (amount || 0).toLocaleString("fr-FR", { maximumFractionDigits: 0 });
        return pos === "after" ? `${value} ${symbol}` : `${symbol} ${value}`;
    }

    priorityStars(priority) {
        const count = parseInt(priority || 0);
        return "★".repeat(count) + "☆".repeat(Math.max(0, 3 - count));
    }
    priorityLabel(priority) {
        if (priority === "3") return "Très urgent";
        if (priority === "2") return "Urgent";
        if (priority === "1") return "Normale";
        return "Basse";
    }
    priorityClass(priority) {
        if (priority === "3") return "tpd-badge tpd-badge-danger";
        if (priority === "2") return "tpd-badge tpd-badge-warning";
        return "tpd-badge tpd-badge-muted";
    }
    stateClass(state, isOverdue) {
        if (isOverdue) return "tpd-badge tpd-badge-danger";
        if (state === "planned") return "tpd-badge tpd-badge-info";
        return "tpd-badge tpd-badge-muted";
    }
    stateLabel(state, isOverdue, stateLabelStr) {
        if (isOverdue) return "En retard";
        return stateLabelStr || state;
    }
    netClass(net) {
        if (net > 0) return "tpd-forecast-positive";
        if (net < 0) return "tpd-forecast-negative";
        return "tpd-forecast-neutral";
    }
    netIcon(net) {
        if (net > 0) return "fa fa-arrow-up";
        if (net < 0) return "fa fa-arrow-down";
        return "fa fa-minus";
    }
    barWidth(amount, max) {
        if (!max || max === 0) return 0;
        return Math.min(100, Math.round((Math.abs(amount) / max) * 100));
    }

    get maxForecastAmount() {
        if (!this.state.forecast) return 1;
        const months = this.state.forecast.months || [];
        return Math.max(1, ...months.map(m => Math.max(m.payments_amount, m.receipts_amount)));
    }

    // ─── Active list ──────────────────────────────────────────────────────────

    get activeList() {
        if (!this.state.data) return [];
        const tab = this.state.activeTab;
        if (tab === "urgent") return this.state.data.urgent_list || [];
        if (tab === "overdue") return this.state.data.overdue_list || [];
        if (tab === "upcoming") return this.state.data.upcoming_list || [];
        return [];
    }
    get activeListEmpty() { return this.activeList.length === 0; }
    get tabEmptyMessage() {
        if (this.state.activeTab === "urgent") return "Aucun paiement urgent en instance.";
        if (this.state.activeTab === "overdue") return "Aucun paiement en retard. Excellent !";
        if (this.state.activeTab === "upcoming") return "Aucun paiement prévu dans les 7 prochains jours.";
        return "";
    }

    _fallbackData() {
        return {
            pending: { count: 0, amount: 0 },
            urgent: { count: 0, amount: 0 },
            overdue: { count: 0, amount: 0 },
            upcoming: { count: 0, amount: 0 },
            urgent_list: [],
            overdue_list: [],
            upcoming_list: [],
            journal_balances: [],
            company: { currency_symbol: "FCFA", currency_position: "after" },
            today: "",
        };
    }
}

registry.category("actions").add("treasury_payment_dashboard", TreasuryPaymentDashboard);
