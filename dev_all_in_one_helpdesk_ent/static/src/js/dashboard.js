/** @odoo-module */
import { registry } from '@web/core/registry';
import { useService } from "@web/core/utils/hooks";
const { Component, onWillStart, onMounted, useState } = owl
import { rpc } from "@web/core/network/rpc";
// import { jsonrpc } from "@web/core/network/rpc_service";
import { _t } from "@web/core/l10n/translation";
import { loadJS } from "@web/core/assets";

export class HelpdeskDashboard extends Component {

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.rpc = this.env.services.rpc
        this.state = useState({
            rowsPerPage: 5,
            currentPage:1,totalrows: 0, 
            currentempPage:1,totaluprows: 0,
            // view_id: null,
            // company_currency: ' '
            
        })
        onWillStart(this.onWillStart);
        onMounted(this.onMounted);
    }

    async onWillStart() {
       await this.fetch_data();
       await this.getGreetings()
       await loadJS("https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js")
    }

    async onMounted() {
        if (this.is_configured){
           var warning = document.getElementById("AlertBox");
           warning.style.display = "none"
       }
       this._onchangeStagesChart();
       this._onchangeTeamChart();
       this._onchangePriorityChart();
       this._onchangeSourceChart();
       this.render_all_ticket_data(this.state.rowsPerPage, this.state.currentPage);
        this.render_upcoming_table_data(this.state.rowsPerPage, this.state.currentempPage);
       this.render_helpdesk_etp_filter();
    }

    async getGreetings() {
        var self = this;
        const now = new Date();
        const hours = now.getHours();
        if (hours >= 5 && hours < 12) {
            self.greetings = "Good Morning";
        }
        else if (hours >= 12 && hours < 18) {
            self.greetings = "Good Afternoon";
        }
        else {
            self.greetings = "Good Evening";
        }
    }

    downloadReport(e) {
        window.print();
    }

    _downloadChart(e) {
        const chart = e.target.offsetParent.children[2].children[0]; // Get the chart canvas element
        const imageDataURL = chart.toDataURL('image/png'); // Generate image data URL
        const filename = chart.id+'HelpdeskDashboard.png'; // Set your preferred filename
        const link = document.createElement('a');
        link.href = imageDataURL;
        link.download = filename;
        link.click();
    }

    // -----------------filter----------------

    // render_helpdesk_etp_filter() {
    //     jsonrpc('/all_helpdesk_etp_filter').then(function (data) {
            // var teams = data[0]
            // var users = data[1]
            // var partners = data[2]
            // var stages = data[3]
            // var durations=data[4]

    //         $(teams).each(function (team) {
    //             $('#team_selection').append("<option value=" + teams[team].id + ">" + teams[team].name + "</option>");
    //         });
    //         $(users).each(function (user) {
    //             $('#user_selections').append("<option value=" + users[user].id + ">" + users[user].name + "</option>");
    //         });
    //         $(partners).each(function (partner) {
    //             $('#partner_selection').append("<option value=" + partners[partner].id + ">" + partners[partner].name + "</option>");
    //         });
    //         $(stages).each(function (stage) {
    //             $('#stages_selection').append("<option value=" + stages[stage].id + ">" + stages[stage].name + "</option>");
    //         });
    //         $(durations).each(function (duration) {
    //             $('#duration_selection').append("<option value=" + durations[duration].id + ">" + durations[duration].name + "</option>");
    //         });

    //     })
    // }
    render_helpdesk_etp_filter() {
        rpc('/all_helpdesk_etp_filter').then(function (data) {
            var teams = data[0]
            var users = data[1]
            var partners = data[2]
            var stages = data[3]
            var durations=data[4]

        teams.forEach(team => {
			const option = document.createElement('option');
			option.value = team.id;
			option.textContent = team.name;
			document.querySelector('#team_selection').appendChild(option);
		});
		
		users?.forEach(user => {
			const option = document.createElement('option');
			option.value = user?.id;
			option.textContent = user?.name;
			document.querySelector('#user_selections')?.appendChild(option);
		});

        partners.forEach(partner => {
			const option = document.createElement('option');
			option.value = partner.id;
			option.textContent = partner.name;
			document.querySelector('#partner_selection').appendChild(option);
		});
		
		stages?.forEach(stage => {
			const option = document.createElement('option');
			option.value = stage?.id;
			option.textContent = stage?.name;
			document.querySelector('#stages_selection')?.appendChild(option);
		});

        })
    }
    
    _onchangeHelpdeskFilter(ev) {
        this.flag = 1
        
        var team_selection = document.querySelector('#team_selection').value
        var user_selections = document.querySelector('#user_selections').value
        var partner_selection = document.querySelector('#partner_selection').value
        var stages_selection = document.querySelector('#stages_selection').value
        var duration_selection = document.querySelector('#duration_selection').value

        this._onchangeStagesChart();
        this._onchangeTeamChart();
        this._onchangePriorityChart();
        this._onchangeSourceChart();
        this.render_all_ticket_data(this.state.rowsPerPage, this.state.currentPage);
        this.render_upcoming_table_data(this.state.rowsPerPage, this.state.currentempPage);
        var self = this;
        
        rpc('/helpdesk-etp/filter-apply', {
            'data': {
                'team': team_selection,
                'user': user_selections,
                'partner': partner_selection,
                'stage': stages_selection,
                'duration': duration_selection,
            }
        }).then(function (data) {

            		    // count box click that time pass data
                        
            self.solve_ticket_data = data['solve_ticket_data']
            self.cancel_ticket_data = data['cancel_ticket_data']
            self.all_ticket_data = data['all_ticket_data']
            self.in_progress_ticket_data = data['in_progress_ticket_data']
            
            			// after change value display on xml side count

            document.querySelector('#solve_ticket_data').innerHTML = data['solve_ticket_data'].length
            document.querySelector('#cancel_ticket_data').innerHTML = data['cancel_ticket_data'].length
            document.querySelector('#all_ticket_data').innerHTML = data['all_ticket_data'].length
            document.querySelector('#in_progress_ticket_data').innerHTML = data['in_progress_ticket_data'].length
            
        })
    }

    // counters-------------------------------

    // fetch_data() 
    // {
    //     this.flag = 0
    //     var self = this;
    //     var def1 = jsonrpc('/get/helpdesk-etp/tiles/data').then(function (result) 
    //     {
    //         console.log(result);
            // self.is_configured = result['is_configured']
            // self.solve_ticket_data = result['solve_ticket_data']
            // self.cancel_ticket_data = result['cancel_ticket_data']
            // self.all_ticket_data = result['all_ticket_data']
            // self.in_progress_ticket_data = result['in_progress_ticket_data']
            // self.user_name = result['user_name']
            // self.user_img = result['user_img']
    //     });
    //     return $.when(def1);
    // }
    async fetch_data() 
    {
        this.flag = 0
        var self = this;
        const result = await rpc('/get/helpdesk-etp/tiles/data');
        self.is_configured = result['is_configured']
        self.solve_ticket_data = result['solve_ticket_data']
        self.cancel_ticket_data = result['cancel_ticket_data']
        self.all_ticket_data = result['all_ticket_data']
        self.in_progress_ticket_data = result['in_progress_ticket_data']
        self.user_name = result['user_name']
        self.user_img = result['user_img']
        return result;
    }

    action_all_ticket(e) {
        e.stopPropagation();
        e.preventDefault();
        var options = {
            on_reverse_breadcrumb: this.on_reverse_breadcrumb,
        };
        //		if (this.flag == 0) {
        var rec_id = e.currentTarget.getAttribute('rec-id');
        var action = e.currentTarget.id || false;
        var domain = false;

        if (action == 'solve_ticket_data1') {
            domain = [["id", "in", this.solve_ticket_data]];
        } else if (action == 'cancel_ticket_data1') {
            domain = [["id", "in", this.cancel_ticket_data]]
        } else if (action == 'all_ticket_data1') {
            domain = [["id", "in", this.all_ticket_data]]
        } else if (action == 'in_progress_ticket_data1') {
            domain = [["id", "in", this.in_progress_ticket_data]]
        } else if (rec_id != 'undefined') {
            domain = [["id", "=", rec_id]]
        }
    
        this.action.doAction({
            name: _t(" All Tickets"),
            type: 'ir.actions.act_window',
            res_model: 'helpdesk.ticket',
            domain: domain,
            view_mode: 'list,form',
            views: [
                [false, 'list'],
                [false, 'form']
            ],
            target: 'current'
        }, options)
        
    }

    // chart11111111111111111111

    async _onchangeStagesChart(ev)
    {
        var team_selection = document.querySelector('#team_selection').value
        var user_selections = document.querySelector('#user_selections').value
        var partner_selection = document.querySelector('#partner_selection').value
        var stages_selection = document.querySelector('#stages_selection').value
        var duration_selection = document.querySelector('#duration_selection').value
        var stages_chart_selection = document.querySelector('#stages_chart_selection').value
        var self = this;
        await rpc("/stages/chart/data",
        {
        'data':
            {
                'team_id': team_selection, 
                'user_id': user_selections,
                'partner_id': partner_selection,
                'stage_id': stages_selection,
                'duration':duration_selection,
            }
        }).then(function (data)
        {
            var ctx = document.querySelector("#stages_chart_data");
            new Chart(ctx, {
                type: stages_chart_selection,
                data: data.stages_chart_data,
                options: {
                    maintainAspectRatio: false,
                     responsive : true,
                                    
                    onClick: (evt, elements) => {
                        if (elements.length > 0) {
                            const element = elements[0];
                            const clickedIndex = element.index;
                            const clickedLabel = data.stages_chart_data.labels[clickedIndex];
                            const clickedValue = data.stages_chart_data.datasets[0].detail[clickedIndex]
                            var options = {
                            };
                            self.action.doAction({
                                name: _t(clickedLabel),
                                type: 'ir.actions.act_window',
                                res_model: 'helpdesk.ticket',
                                domain: [["id", "in", clickedValue]],
                                view_mode: 'list,form',
                                views: [
                                    [false, 'list'],
                                    [false, 'form']
                                ],
                                target: 'current'
                            }, options)
                        } else {
                        }
                    }
                }
            });
        });
    }

    // -----------chart222222--------

    async _onchangeTeamChart(ev)
    {
        var team_selection = document.querySelector('#team_selection').value
        var user_selections = document.querySelector('#user_selections').value
        var partner_selection = document.querySelector('#partner_selection').value
        var stages_selection = document.querySelector('#stages_selection').value
        var duration_selection = document.querySelector('#duration_selection').value
        var helpdesk_team_chart_selection=document.querySelector('#helpdesk_team_chart_selection').value
        var self = this;
        await rpc("/team/chart/data",
        {
        'data':
            {
                'team_id': team_selection, 
                'user_id': user_selections,
                'partner_id': partner_selection,
                'stage_id': stages_selection,
                'duration':duration_selection,
            }
        }).then(function (data)
        {
            var ctx = document.querySelector("#helpdesk_team_chart_data");
            new Chart(ctx, {
                type: helpdesk_team_chart_selection,
                data: data.helpdesk_team_chart_data,
                options: {
                    maintainAspectRatio: false,
                    
                    onClick: (evt, elements) => {
                        if (elements.length > 0) {
                            const element = elements[0];
                            const clickedIndex = element.index;
                            const clickedLabel = data.helpdesk_team_chart_data.labels[clickedIndex];
                            const clickedValue = data.helpdesk_team_chart_data.datasets[0].detail[clickedIndex]
                            var options = {
                            };
                            self.action.doAction({
                                name: _t(clickedLabel),
                                type: 'ir.actions.act_window',
                                res_model: 'helpdesk.ticket',
                                domain: [["id", "in", clickedValue]],
                                view_mode: 'list,form',
                                views: [
                                    [false, 'list'],
                                    [false, 'form']
                                ],
                                target: 'current'
                            }, options)
                        } else {
                        }
                    }
                }
            });
        });
    }

    // -----------chart33333--------

    async _onchangePriorityChart(ev)
    {
        var team_selection = document.querySelector('#team_selection').value
        var user_selections = document.querySelector('#user_selections').value
        var partner_selection = document.querySelector('#partner_selection').value
        var stages_selection = document.querySelector('#stages_selection').value
        var duration_selection = document.querySelector('#duration_selection').value
        var helpdesk_priority_chart_selection=document.querySelector('#helpdesk_priority_chart_selection').value
        var self = this;
        await rpc("/priority/chart/data",
        {
        'data':
            {
                'team_id': team_selection, 
                'user_id': user_selections,
                'partner_id': partner_selection,
                'stage_id': stages_selection,
                'duration':duration_selection,
            }
        }).then(function (data)
        {
            var ctx = document.querySelector("#helpdesk_priority_chart_data");
            new Chart(ctx, {
                type: helpdesk_priority_chart_selection,
                data: data.helpdesk_priority_chart_data,
                options: {
                    maintainAspectRatio: false,

                    onClick: (evt, elements) => {
                        if (elements.length > 0) {
                            const element = elements[0];
                            const clickedIndex = element.index;
                            const clickedLabel = data.helpdesk_priority_chart_data.labels[clickedIndex];
                            const clickedValue = data.helpdesk_priority_chart_data.datasets[0].detail[clickedIndex]
                            var options = {
                            };
                            self.action.doAction({
                                name: _t(clickedLabel),
                                type: 'ir.actions.act_window',
                                res_model: 'helpdesk.ticket',
                                domain: [["id", "in", clickedValue]],
                                view_mode: 'list,form',
                                views: [
                                    [false, 'list'],
                                    [false, 'form']
                                ],
                                target: 'current'
                            }, options)
                        } else {
                        }
                    }
                }
            });
        });
    }

    // -----------chart44444--------

    async _onchangeSourceChart(ev)
    {
        var team_selection = document.querySelector('#team_selection').value
        var user_selections = document.querySelector('#user_selections').value
        var partner_selection = document.querySelector('#partner_selection').value
        var stages_selection = document.querySelector('#stages_selection').value
        var duration_selection = document.querySelector('#duration_selection').value
        var helpdesk_source_chart_selection=document.querySelector('#helpdesk_source_chart_selection').value
        var self = this;
        await rpc("/source/chart/data",
        {
        'data':
            {
                'team_id': team_selection, 
                'user_id': user_selections,
                'partner_id': partner_selection,
                'stage_id': stages_selection,
                'duration':duration_selection,
            }
        }).then(function (data)
        {
            var ctx = document.querySelector("#helpdesk_source_chart_data");
            new Chart(ctx, {
                type: helpdesk_source_chart_selection,
                data: data.helpdesk_source_chart_data,
                options: {
                    maintainAspectRatio: false,

                    onClick: (evt, elements) => {
                        if (elements.length > 0) {
                            const element = elements[0];
                            const clickedIndex = element.index;
                            const clickedLabel = data.helpdesk_source_chart_data.labels[clickedIndex];
                            const clickedValue = data.helpdesk_source_chart_data.datasets[0].detail[clickedIndex]
                            var options = {
                            };
                            self.action.doAction({
                                name: _t(clickedLabel),
                                type: 'ir.actions.act_window',
                                res_model: 'helpdesk.ticket',
                                domain: [["id", "in", clickedValue]],
                                view_mode: 'list,form',
                                views: [
                                    [false, 'list'],
                                    [false, 'form']
                                ],
                                target: 'current'
                            }, options)
                        } else {
                        }
                    }
                }
            });
        });
    }

    async render_all_ticket_data(rowsPerPage,page) {

        var team_selection = document.querySelector('#team_selection').value
        var user_selections = document.querySelector('#user_selections').value
        var partner_selection = document.querySelector('#partner_selection').value
        var stages_selection = document.querySelector('#stages_selection').value
        var duration_selection = document.querySelector('#duration_selection').value
                
        var self = this;

        await rpc("/helpdesk/table/data", {
            'data': {
                
                'team_id': team_selection, 
                'user_id': user_selections,
                'partner_id': partner_selection,
                'stage_id': stages_selection,
                'duration':duration_selection,
                                
            }
        }).then(function (data) 
        {
            
            var all_team_list = data['all_team_list'];
            self.state.totalrows = all_team_list.length;
            var tbody = document.querySelector("#my_table_all_team_list tbody");
            tbody.innerHTML = '';
            
            const start = (page - 1) * rowsPerPage;
            const end = start + rowsPerPage;
            const paginatedData = all_team_list.slice(start, end)
            
            for (var i = 0; i < paginatedData.length; i++) {
                // Create a new row
                var row = document.createElement("tr");
                // Create cells for each property in the object
                for (var key in paginatedData[i]) {
                    if (key !== 'id') {
                        var cell = document.createElement("td");
                        cell.classList.add("center-text");
                        if (paginatedData[i][key].length == 2) {
                            cell.textContent = paginatedData[i][key][1];
                            row.appendChild(cell);
                        }
                        
                        else if(key==='create_date')
                            {
                                var cell = document.createElement("td");
                                var create_date=paginatedData[i]['create_date']
                                if(create_date)
                                {
                                     var arr1 = create_date.split('-');
                                     cell.textContent = arr1[2] + '-' + arr1[1] + '-' + arr1[0];
                                 }
                                 else
                                 {
                                    cell.textContent='-'
                                 }
                                 row.appendChild(cell);
                            }

                        else {
                            if (paginatedData[i][key] == false) {
                                cell.textContent = '-';
                                row.appendChild(cell);
                            } else {
                                cell.textContent = paginatedData[i][key];
                                row.appendChild(cell);
                            }
                        }
                        
                    }
                }
            var buttonCell = document.createElement("td");
    		var button = document.createElement("button");
    		button.textContent = "View";
    		button.setAttribute("data-id", paginatedData[i].id);
    		button.addEventListener("click", function() {
		    var id = this.getAttribute("data-id");
				// Call your function with the ID
				team_tree_button_function(id);
			});
    		button.style.backgroundColor = "Pink";
    		button.style.color = "black";
    		button.style.padding = "6px 12px";
    		buttonCell.appendChild(button);
    		row.appendChild(buttonCell);
            tbody.appendChild(row);
            }
            
        	function team_tree_button_function(id) {
				var options = {
				};
				self.action.doAction({
				    name: _t("All Team"),
				    type: 'ir.actions.act_window',
				    res_model: 'helpdesk.ticket',
				    domain: [["id", "=", id]],
				    view_mode: 'list,form',
				    views: [
				        [false, 'list'],
				        [false, 'form']
				    ],
				    target: 'current'
				}, options)
			}
        })
    }
    prevPage(e) {

        if (this.state.currentPage > 1) {
            this.state.currentPage--;
            this.render_all_ticket_data(this.state.rowsPerPage, this.state.currentPage);
            document.getElementById("next_button").disabled = false;
        }
        if (this.state.currentPage == 1)
        {
            document.getElementById("prev_button").disabled = true;
        } else {
            document.getElementById("prev_button").disabled = false;
        }
    }
        nextPage() {
        if ((this.state.currentPage * this.state.rowsPerPage) < this.state.totalrows) {
            this.state.currentPage++;
            this.render_all_ticket_data(this.state.rowsPerPage, this.state.currentPage);
            document.getElementById("prev_button").disabled = false;
        }
        if (Math.ceil(this.state.totalrows / this.state.rowsPerPage) == this.state.currentPage)
        {
            document.getElementById("next_button").disabled = true;
        } else {
            document.getElementById("next_button").disabled = false;
        }
    }

    async render_upcoming_table_data(rowsPerPage,page) {
        var team_selection = document.querySelector('#team_selection').value
        var user_selections = document.querySelector('#user_selections').value
        var partner_selection = document.querySelector('#partner_selection').value
        var stages_selection = document.querySelector('#stages_selection').value
        var duration_selection = document.querySelector('#duration_selection').value
        var self = this;

        await rpc("/helpdesk/table/data", {
            'data': {
                
                'team_id': team_selection, 
                'user_id': user_selections,
                'partner_id': partner_selection,
                'stage_id': stages_selection,
                'duration':duration_selection,
                                
            }
        }).then(function (data) 
        {      
            var closing_ticket_list = data['closing_ticket_list'];
            self.state.totalemprows = closing_ticket_list.length;
            var tbody = document.querySelector("#my_table_closing_ticket_list tbody");
            tbody.innerHTML = '';
            
            const strt = (page - 1) * rowsPerPage;
            const eend = strt + rowsPerPage;
            const paginatdData = closing_ticket_list.slice(strt, eend)
            
            for (var i = 0; i < paginatdData.length; i++) {
                // Create a new row
                var row = document.createElement("tr");
                // Create cells for each property in the object
                for (var key in paginatdData[i]) {
                    if (key !== 'id') {
                        var cell = document.createElement("td");
                        cell.classList.add("center-text");
                        if (paginatdData[i][key].length == 2) {
                            cell.textContent = paginatdData[i][key][1];
                            row.appendChild(cell);
                        }
                        
                        else if(key==='date_deadline')
                            {
                                var cell = document.createElement("td");
                                var date_deadline=paginatdData[i]['date_deadline']
                                if(date_deadline)
                                {
                                     var arr1 = date_deadline.split('-');
                                     cell.textContent = arr1[2] + '-' + arr1[1] + '-' + arr1[0];
                                 }
                                 else
                                 {
                                    cell.textContent='-'
                                 }
                                 row.appendChild(cell);
                            }

                        else {
                            if (paginatdData[i][key] == false) {
                                cell.textContent = '-';
                                row.appendChild(cell);
                            } else {
                                cell.textContent = paginatdData[i][key];
                                row.appendChild(cell);
                            }
                        }

                    }
                }
            var buttonCell = document.createElement("td");
    		var button = document.createElement("button");
    		button.textContent = "View";
    		button.setAttribute("data-id", paginatdData[i].id);
    		button.addEventListener("click", function() {
		    var id = this.getAttribute("data-id");
				// Call your function with the ID
				upcoming_tree_button_function(id);
			});
    		button.style.backgroundColor = "Pink";
    		button.style.color = "black";
    		button.style.padding = "6px 12px";
    		buttonCell.appendChild(button);
    		row.appendChild(buttonCell);
            tbody.appendChild(row);
            }
            
        	function upcoming_tree_button_function(id) {
				var options = {
				};
				self.action.doAction({
				    name: _t("All Tickets"),
				    type: 'ir.actions.act_window',
				    res_model: 'helpdesk.ticket',
				    domain: [["id", "=", id]],
				    view_mode: 'list,form',
				    views: [
				        [false, 'list'],
				        [false, 'form']
				    ],
				    target: 'current'
				}, options)
			}

        })
    }
    prevsPage(e) {

        if (this.state.currentempPage > 1) {
            this.state.currentempPage--;
            this.render_upcoming_table_data(this.state.rowsPerPage, this.state.currentempPage);
            document.getElementById("nextt_button").disabled = false;
        }
        if (this.state.currentempPage == 1)
        {
            document.getElementById("prevs_button").disabled = true;
        } else {
            document.getElementById("prevs_button").disabled = false;
        }
    }
        nexttPage() {
        if ((this.state.currentempPage * this.state.rowsPerPage) < this.state.totalemprows) {
            this.state.currentempPage++;
            this.render_upcoming_table_data(this.state.rowsPerPage, this.state.currentempPage);
            document.getElementById("prevs_button").disabled = false;
        }
        if (Math.ceil(this.state.totalemprows / this.state.rowsPerPage) == this.state.currentempPage)
        {
            document.getElementById("nextt_button").disabled = true;
        } else {
            document.getElementById("nextt_button").disabled = false;
        }
    }

}                          
HelpdeskDashboard.template = "helpdeskdashboard"
registry.category("actions").add("open_helpdesk_dashboard", HelpdeskDashboard)
