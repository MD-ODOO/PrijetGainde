/** @odoo-module **/

import { registry } from "@web/core/registry";
import { legacyAction } from "@web/legacy/legacy_action";
import { AbstractAction } from "@web/legacy/js/views/abstract_action";
import { _t } from "@web/core/l10n/translation";
import { renderToString } from "@web/core/utils/render";
import { rpc } from "@web/core/network/rpc";
import { session } from "@web/session";

const MONTHS = [
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
];

const TreasuryKpiDashboard = AbstractAction.extend({
    template: "treasury_management.TreasuryKpiDashboard",
    events: {
        "change .o_year_input": "_onYearChange",
    },

    init: function (parent, action) {
        this._super.apply(this, arguments);
        this.year = new Date().getFullYear();
        this.data = null;
        this.chart = null;
    },

    willStart: function () {
        return this._loadData();
    },

    start: function () {
        const res = this._super.apply(this, arguments);
        this._renderView();
        return res;
    },

    destroy: function () {
        this._destroyChart();
        return this._super.apply(this, arguments);
    },

    _onYearChange: function (ev) {
        const year = parseInt(ev.currentTarget.value, 10);
        if (!isNaN(year)) {
            this.year = year;
            this._loadData().then(this._renderView.bind(this));
        }
    },

    _loadData: function () {
        const companyId =
            session.company_id ||
            (session.user_context &&
                Array.isArray(session.user_context.allowed_company_ids) &&
                session.user_context.allowed_company_ids.length
                ? session.user_context.allowed_company_ids[0]
                : false);

        return rpc("/web/dataset/call_kw/treasury.kpi/get_dashboard_data", {
            model: "treasury.kpi",
            method: "get_dashboard_data",
            args: [],
            kwargs: { year: this.year, company_id: companyId },
        })
            .then((data) => {
                this.data = data;
            })
            .catch((err) => {
                console.error(err);
                this.do_warn(
                    _t("Impossible de charger le tableau de bord."),
                    err && err.message ? err.message : ""
                );
            });
    },

    _renderView: function () {
        if (!this.data) {
            this.$el.html(
                '<div class="o_text_center o_py_4"><i class="fa fa-spinner fa-spin"></i></div>'
            );
            return;
        }
        const context = {
            year: this.year,
            data: this.data,
            summaryCards: this._getSummaryCards(),
            tableRows: this._getTableRows(),
            formatCurrency: this._formatCurrency.bind(this),
        };
        this.$el.html(renderToString("treasury_management.TreasuryKpiDashboard", context));
        this._renderChart();
    },

    _getSummaryCards: function () {
        const s = this.data.summary || {};
        return [
            { key: "revenue", label: _t("Revenu actuel"), value: s.revenue || 0 },
            { key: "receivables", label: _t("Créances clients"), value: s.receivables || 0 },
            { key: "expenses", label: _t("Dépenses courantes"), value: s.expenses || 0 },
            { key: "debts", label: _t("Dettes"), value: s.debts || 0 },
        ];
    },

    _getTableRows: function () {
        const revenue = this.data.series.revenue || [];
        const expenses = this.data.series.expenses || [];
        return revenue.map((r, idx) => {
            const exp = expenses[idx] || { value: 0 };
            const delta = (r.value || 0) - (exp.value || 0);
            return {
                month: MONTHS[(r.label || 1) - 1] || r.label,
                revenue: r.value || 0,
                expenses: exp.value || 0,
                delta: delta,
            };
        });
    },

    _formatCurrency: function (amount) {
        const company = this.data ? this.data.company : null;
        const symbol = company ? company.currency_symbol : "";
        const pos = company ? company.currency_position : "before";
        const formatted = (amount || 0).toLocaleString(undefined, {
            minimumFractionDigits: 0,
            maximumFractionDigits: 0,
        });
        return pos === "after" ? formatted + symbol : symbol + formatted;
    },

    _renderChart: function () {
        if (!this.data || typeof Chart === "undefined") {
            return;
        }
        const canvas = this.$("#treasury-kpi-chart")[0];
        if (!canvas) return;
        this._destroyChart();

        const revenue = this.data.series.revenue || [];
        const expenses = this.data.series.expenses || [];
        const labels = revenue.map((m) => MONTHS[(m.label || 1) - 1] || m.label);
        const revenueValues = revenue.map((m) => m.cumulative || 0);
        const expenseValues = expenses.map((m) => m.cumulative || 0);

        this.chart = new Chart(canvas, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: _t("Facturé"),
                        data: revenueValues,
                        borderColor: "#3b82f6",
                        backgroundColor: "rgba(59,130,246,0.2)",
                        tension: 0.25,
                        fill: true,
                    },
                    {
                        label: _t("Dépenses"),
                        data: expenseValues,
                        borderColor: "#ef4444",
                        backgroundColor: "rgba(239,68,68,0.15)",
                        tension: 0.25,
                        fill: true,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { grid: { display: false } },
                    y: {
                        ticks: {
                            callback: function (val) {
                                return (val || 0).toLocaleString();
                            },
                        },
                    },
                },
                plugins: {
                    legend: { position: "bottom" },
                    tooltip: {
                        callbacks: {
                            label: (context) =>
                                `${context.dataset.label}: ${this._formatCurrency(context.parsed.y)}`,
                        },
                    },
                },
            },
        });
    },

    _destroyChart: function () {
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
    },
});

// Register in the new OWL action registry (Odoo 17/18 webclient)
registry
    .category("actions")
    .add("treasury_kpi_dashboard", TreasuryKpiDashboard);
