frappe.provide("frappe.integration_service")

frappe.ui.form.on('AuthorizeNet Settings', {
	refresh: function(frm) {
	
	},  
	/*get_data: function(frm) {
        console.log("sync ordr click 11:14:56")                
        frappe.call({
            method: "erpnext.erpnext_integrations.doctype.magento_setting.magento_setting.magento_sync12",       
            args: {},   
            callback: function(r) {
                console.log(r.message);
            },
            freeze: true,        
            freeze_message: "Syncing eBay customers and orders; this may take some time..."
        });           
    } */   
});   

frappe.integration_service.authorizenet_settings =  Class.extend({
	init: function(frm) {

	},

	get_scheduler_job_info: function() {
		return  {}
	},

	get_service_info: function(frm) {
		frappe.call({
			method: "authorizenet.authorizenet.doctype.authorizenet_settings.authorizenet_settings.get_service_details",
			callback: function(r) {
				var integration_service_help = frm.fields_dict.integration_service_help.wrapper;
				$(integration_service_help).empty();
				$(integration_service_help).append(r.message);
			}
		})
	}
})
