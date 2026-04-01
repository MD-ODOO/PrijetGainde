/** @odoo-module **/
import { rpc } from "@web/core/network/rpc";

//odoo.define('dev_helpdesk_tracking.web_portal', function (require) {
//'use strict';
    
  //  require('web.dom_ready');
   //var ajax = require('web.ajax');
   

if($('.tracking-input-container').length){
	$(".confirm_track_ticket").click(function () {
		var tracking_number     = $('.tracking-ticket-number-input').val();
		
		if(!tracking_number){
			alert("Enter Tracking Number");
		}
		rpc("/dev_helpdesk_ticket_track",{
        	'do_no':tracking_number
        },{'async':false}).then(function(res){
        	if(res){
        		$('.dev-tracking-container').removeClass('d-none');
        		$('.delivery-order-status').text(res.status)
        		$('.customer-delivery-order-status').text(res.customer)
        		$('.ticket-number-status').text(res.ticket_number)
        		$('.ticket-name-status').text(res.ticket_name)
        		$('.address-street').text(res.street)
        		$('.address-street-two').text(res.street2)
        		$('.address-street-city').text(res.city)
        		$('.dev-none-tracking-container').addClass('d-none');
        		if (!res.street){
        		    $('.address-street').addClass('d-none')
        		}
        		if (!res.street2){
        		    $('.address-street-two').addClass('d-none')
        		}
        		if (!res.city){
        		    $('.address-street-city').addClass('d-none')
        		}
        	}
        	if(!res){
        	    $('.dev-tracking-container').addClass('d-none');
        	    $('.dev-none-tracking-container').removeClass('d-none');
        	    
        	    
        	}
        });
		
	});
}
    
//});
