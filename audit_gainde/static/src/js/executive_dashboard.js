/** @odoo-module **/

import { Component, onWillStart, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class RiskDashboard extends Component {

    setup(){

        this.orm = useService("orm");
        this.action = useService("action");

        this.data = {};

        onWillStart(async () => {

            this.data = await this.orm.call(
                "audit_gainde.risk",
                "get_dashboard_data",
                []
            );

        });

        onMounted(() => {

            this.renderTopRisks();
            this.renderLevels();
            this.renderDomains();

        });
    }

    renderTopRisks(){

    const labels = this.data.top_risks.map(r => r.code);
    const values = this.data.top_risks.map(r => r.count);

    const self = this;

    new Chart(document.getElementById("topRisks"),{

        type:"bar",

        data:{
            labels:labels,
            datasets:[{
                label:"Top risques utilisés",
                data:values
            }]
        },

        options:{
            onClick(evt, elements){

                if(elements.length){

                    const index = elements[0].index;
                    const code = labels[index];

                    self.action.doAction({
                        type:"ir.actions.act_window",
                        name:"Risques",
                        res_model:"audit_gainde.risk",
                        views:[[false,"list"],[false,"form"]],
                        domain:[["code","=",code]]
                    });

                }

            }
        }

    });

}

    renderLevels(){

    const labels = this.data.levels.map(l => l.level);
    const values = this.data.levels.map(l => l.count);

    const self = this;

    new Chart(document.getElementById("riskLevels"),{

        type:"doughnut",

        data:{
            labels:labels,
            datasets:[{
                data:values
            }]
        },

        options:{
            onClick(evt, elements){

                if(elements.length){

                    const index = elements[0].index;
                    const level = labels[index];

                    self.action.doAction({
                        type:"ir.actions.act_window",
                        name:"Risques",
                        res_model:"audit_gainde.risk",
                        views:[[false,"list"],[false,"form"]],
                        domain:[["level","=",level]]
                    });

                }

            }
        }

    });

}

    renderDomains(){

    const labels = this.data.domains.map(d => d.domain);
    const values = this.data.domains.map(d => d.count);

    const self = this;

    new Chart(document.getElementById("riskDomains"),{

        type:"bar",

        data:{
            labels:labels,
            datasets:[{
                label:"Risques par domaine",
                data:values
            }]
        },

        options:{
            onClick(evt, elements){

                if(elements.length){

                    const index = elements[0].index;
                    const domain = labels[index];

                    self.action.doAction({
                        type:"ir.actions.act_window",
                        name:"Risques",
                        res_model:"audit_gainde.risk",
                        views:[[false,"list"],[false,"form"]],
                        domain:[["domain","=",domain]]
                    });

                }

            }
        }

    });

}
    openAllRisks(){

    this.action.doAction({
        type: "ir.actions.act_window",
        name: "Risques",
        res_model: "audit_gainde.risk",
        views: [[false, "list"], [false, "form"]],
        domain: []
    });

}

openCriticalRisks(){

    this.action.doAction({
        type: "ir.actions.act_window",
        name: "Risques critiques",
        res_model: "audit_gainde.risk",
        views: [[false, "list"], [false, "form"]],
        domain: [["level","=","critical"]]
    });

}

openUsedRisks(){

    this.action.doAction({
        type: "ir.actions.act_window",
        name: "Risques utilisés",
        res_model: "audit_gainde.risk",
        views: [[false, "list"], [false, "form"]],
        domain: [["mission_ids","!=",false]]
    });

}

openNoControlRisks(){

    this.action.doAction({
        type: "ir.actions.act_window",
        name: "Risques sans contrôle",
        res_model: "audit_gainde.risk",
        views: [[false, "list"], [false, "form"]],
        domain: [["control_ids","=",false]]
    });

}

}

RiskDashboard.template = "audit_gainde.RiskDashboard";

registry.category("actions").add("risk_dashboard", RiskDashboard);