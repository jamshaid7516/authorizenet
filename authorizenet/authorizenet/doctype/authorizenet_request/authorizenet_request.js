// Copyright (c) 2016, DigiThinkIT, Inc. and contributors
// For license information, please see license.txt

frappe.ui.form.on('AuthorizeNet Request', {
	refresh: function(frm) {
		//console.log("show href");
		//console.log(window.location.host);
		//console.log(window.location.hostname)
		if(frm.doc.status=='Issued' || frm.doc.status=='Error' ){
			frm.add_custom_button("open Payment link", function(){ 
				//console.log(frm.doc.status); 
				var ss=window.location.host 
				var url1="http://"+window.location.host+"/integrations/authorizenet_checkout/"+frm.doc.name
				//var url="http://50.116.37.238:8000/integrations/authorizenet_checkout/"+frm.doc.name
				//console.log(url1);  
				//window.open(url, '_blank');  
				var myWin = window.open(url1);
				//window.location.href = "http://google.com"; 
			});                
		}
	}
});                      
