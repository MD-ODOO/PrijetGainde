/** @odoo-module **/

import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';
import { Component, onWillStart, xml } from '@odoo/owl';

/**
 * Function to generate curl command
 */
function generateCurlCommand(url, method, headers, data) {
    let curlCommand = `curl -X ${method.toUpperCase()}`;

    for (const key in headers) {
        if (headers.hasOwnProperty(key)) {
            curlCommand += ` -H "${key}: ${headers[key]}"`;  
        }
    }

    if (method.toUpperCase() === 'POST' || method.toUpperCase() === 'PUT' || method.toUpperCase() === 'PATCH') {
        curlCommand += ` -d '${JSON.stringify(data)}'`;
    }

    curlCommand += ` ${url}`;

    return curlCommand;
}

/**
 * Function to update secure API test result
 */
function update_secure_api_test_result(id, route, method, status, status_text, response, curl_command) {
    return fetch('/secure/api/test/'+id, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json; charset=utf-8',
        },
        body: JSON.stringify({
            params: {
                name: route,
                method: method,
                status: status,
                status_text: status_text,
                response: response,
                curl_command: curl_command,
            }
        }),
    })
    .then(response => response.json())
    .then(data => {

        return data;
    })
    .catch(error => {

        throw error;
    });
}

export class BtnLiveTest extends Component {
    setup() {
        this.actionService = useService('action');
        this.params = this.props.action.params || {};
        
        onWillStart(() => this.processAction());
    }
    
    async processAction() {
        let {
            id, 
            api_action, 
            route, 
            live_test_id, 
            live_test_ids, 
            live_test_model, 
            live_test_data,
            live_test_domain, 
            live_test_offset, 
            live_test_limit, 
            live_test_order,
            live_test_method, 
            is_multi_model, 
            test_id
        } = this.params;
        
        console.log("Live Test this.params", this.params);

        live_test_data = JSON.parse(live_test_data);
        live_test_domain = live_test_domain;             //live_test_domain.replace(/\\"/g, '"');    // should be string
        live_test_offset = parseInt(live_test_offset);
        live_test_limit = parseInt(live_test_limit);

        const default_request_timeout = 10000;
        

        
        let dst_route = route;
        if (is_multi_model) {
            dst_route += "/"+live_test_model;
        }
        

        
        const is_process = (live_test_method == "GET") ? true : false;
        let r_data = live_test_data || {};
        
        // Process data based on API action
        if (api_action == 'search') {
            r_data = {};
            if (live_test_domain) {
                r_data["domain"] = live_test_domain;
            }
            if (live_test_offset) {
                r_data["offset"] = live_test_offset;
            }
            if (live_test_limit) {
                r_data["limit"] = live_test_limit;
            }
            if (live_test_order) {
                r_data["order"] = live_test_order;
            }
        } else if (api_action == 'create') {

        } else if (api_action == 'read') {
            dst_route = dst_route + '/' + live_test_id;
            if (live_test_ids) {
                r_data = {"ids": live_test_ids};
            }
        } else if (api_action == 'update' || api_action == 'delete') {
            if (live_test_id) {
                dst_route = dst_route + '/' + live_test_id;
            }
        } else if (api_action == 'rest') {
            if (live_test_id) {
                dst_route = dst_route + '/' + live_test_id;
            }
            
            if (live_test_ids) {
                r_data = {...r_data, "ids": live_test_ids};
            }
            
            if (live_test_domain) {
                r_data = {...r_data, "domain": live_test_domain};
            }
            if (live_test_offset) {
                r_data = {...r_data, "offset": live_test_offset};
            }
            if (live_test_limit) {
                r_data = {...r_data, "limit": live_test_limit};
            }
            if (live_test_order) {
                r_data = {...r_data, "order": live_test_order};
            }
        } else if (api_action == 'rpc') {
            if (live_test_id) {
                dst_route = dst_route + '/' + live_test_id;
            }
        }
        
        console.log("Live Test request data", r_data);

        // -------------------------
        // | Generate CURL command |
        // -------------------------
        const web_base_url = window.location.protocol + '//' + window.location.hostname + (window.location.port?':'+window.location.port:''); // http://localhost:10001
        
        // Convert the object to URLSearchParams
        const params = new URLSearchParams(r_data);
        // Get the string representation of the parameters
        const paramString = params.toString();
        // Append a '?' if there are parameters
        const queryString = (paramString && is_process) ? `?${paramString}` : '';

        const curl_command = generateCurlCommand(web_base_url+dst_route+queryString, live_test_method, {'Content-Type': 'application/json'}, r_data);
        // -------------------------
        
        try {
            const response = await fetch(dst_route+queryString, {
                method: live_test_method,
                headers: {
                    'Content-Type': 'application/json; charset=utf-8',
                },
                body: is_process ? null : JSON.stringify(r_data),
            });
            
            let responseData;
            try {
                responseData = await response.json();
            } catch (e) {
                console.log("Response error:", e, " | Response:", response);
                responseData = await response.text();
            }
            
            if (response.ok) {
                const maximum_text_length = 300;
                try {
                    if (responseData["error"]) {
                        const rvalue = responseData["error"];
                        if (typeof rvalue === 'string' || rvalue instanceof String) {
                            if (rvalue.length > maximum_text_length) {
                                const short = rvalue.slice(0, maximum_text_length);
                                responseData["error"] = short + "...LONG TEXT (" + rvalue.length + ") WAS TRUNCATED";
                            }                                        
                        }
                    }
                    if (responseData["result"]) {
                        if (Array.isArray(responseData["result"])) {
                            responseData["result"].forEach((i) => {
                                if (typeof i === 'object') {
                                    Object.keys(i).forEach(key => {
                                        const rvalue = i[key];
                                        if (typeof rvalue === 'string' || rvalue instanceof String) {
                                            if (rvalue.length > maximum_text_length) {
                                                const short = rvalue.slice(0, maximum_text_length);
                                                i[key] = short + "...LONG TEXT (" + rvalue.length + ") WAS TRUNCATED";
                                            }                                        
                                        }
                                    });
                                }
                            });
                        } else {
                            Object.keys(responseData["result"]).forEach(key => {
                                const rvalue = responseData["result"][key];
                                if (typeof rvalue === 'string' || rvalue instanceof String) {
                                    if (rvalue.length > maximum_text_length) {
                                        const short = rvalue.slice(0, maximum_text_length);
                                        responseData["result"][key] = short + "...LONG TEXT (" + rvalue.length + ") WAS TRUNCATED";
                                    }                                        
                                }
                            });
                        }
                    }
                } catch (error) {

                }
                

                await update_secure_api_test_result(test_id, dst_route, live_test_method, 200, "OK", responseData, curl_command);
            } else {

                await update_secure_api_test_result(test_id, dst_route, live_test_method, response.status, response.statusText, responseData, curl_command);
            }
        } catch (error) {

            await update_secure_api_test_result(test_id, dst_route, live_test_method, 0, "Network Error", error.toString(), curl_command);
        }
        

        
        this.id = id;
        this.test_id = test_id;
        
        // Navigate to the test form view
        await this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: "secure.api.test",
            res_id: this.test_id,
            views: [[false, 'form']],
            target: 'self'
        }, {
            clearBreadcrumbs: false
        });
    }
}


// Define the props schema for the client action
BtnLiveTest.props = {
    action: { type: Object },
    actionId: { type: Number, optional: true },
    className: { type: String, optional: true },
    updateActionState: { type: Function, optional: true },
};

// Define an empty template for the component
BtnLiveTest.template = xml`<div></div>`;

registry.category('actions').add('btn_live_test', BtnLiveTest);
