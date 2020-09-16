"""
# Integrating Authorize.Net

### 1. Validate Currency Support

Example:

	from frappe.integration_broker.doctype.integration_service.integration_service import get_integration_controller

	controller = get_integration_controller("AuthorizeNet")
	controller().validate_transaction_currency(currency)
  
### 2. Redirect for payment  

Example:   

	payment_details = {
		"amount": 600,
		"title": "Payment for bill : 111",
		"description": "payment via cart",
		"reference_doctype": "Payment Request",
		"reference_docname": "PR0001",
		"payer_email": "NuranVerkleij@example.com",
		"payer_name": "Nuran Verkleij",
		"order_id": "111",
		"currency": "USD"
	}

	# redirect the user to this url
	url = controller().get_payment_url(**payment_details)


### 3. On Completion of Payment

Write a method for `on_payment_authorized` in the reference doctype

Example:

	def on_payment_authorized(payment_status):
		# your code to handle callback

##### Note:

payment_status - payment gateway will put payment status on callback.
For authorize.net status parameter is one from: [Completed, Failed]


More Details:
<div class="small">For details on how to get your API credentials, follow this link: <a href="https://support.authorize.net/authkb/index?page=content&id=A405" target="_blank">https://support.authorize.net/authkb/index?page=content&id=A405</a></div>

"""

from __future__ import unicode_literals
import frappe
from frappe import _, _dict
from frappe.utils import get_url, call_hook_method, flt
from frappe.model.document import Document
from frappe.integrations.utils import create_request_log, create_payment_gateway
import json
from datetime import datetime
import urllib            
import authorize
import urllib.parse
from frappe.utils.password import get_decrypted_password    
import frappe, time, dateutil, math, csv,json,re 
from authorize import AuthorizeResponseError, AuthorizeInvalidError
from authorizenet.utils import get_additional_info,get_shipping_address,get_authorizenet_user, get_card_accronym, authnet_address, get_contact,get_primary_address,get_line_items,get_customer

def log(*args, **kwargs):
	print("\n".join(args))    

class AuthorizeNetSettings(Document):
	service_name = "AuthorizeNet"
	supported_currencies = ["USD"]
	is_embedable = True

	def validate(self):
		create_payment_gateway("AuthorizeNet")
		call_hook_method("payment_gateway_enabled", gateway=self.service_name)
		if not self.flags.ignore_mandatory:
			self.validate_authorizenet_credentails()

	def on_update(self):
		pass

	def get_embed_context(self, context): 
		# list countries for billing address form
		context["authorizenet_countries"] = frappe.get_list("Country", fields=["country_name", "name"], ignore_permissions=1)
		default_country = frappe.get_value("System Settings", "System Settings", "country")
		default_country_doc = next((x for x in context["authorizenet_countries"] if x.name == default_country), None)

		country_idx = context["authorizenet_countries"].index(default_country_doc)
		context["authorizenet_countries"].pop(country_idx)
		context["authorizenet_countries"] = [default_country_doc] + context["authorizenet_countries"]

		context["year"] = datetime.today().year

		# get the authorizenet user record
		#authnet_user = get_authorizenet_user()

		#if authnet_user:
		#	context["stored_payments"] = authnet_user.get("stored_payments", [])

	def get_embed_form(self, context={}):

		context.update({
			"source": "templates/includes/integrations/authorizenet/embed.html"
		})
		context = _dict(context)

		self.get_embed_context(context)

		return {
			"form": frappe.render_template(context.source, context),
			"style_url": "/assets/css/authorizenet_embed.css",
			"script_url": "/assets/js/authorizenet_embed.js"
		}

	def validate_authorizenet_credentails(self):
		pass

	def validate_transaction_currency(self, currency):
		if currency not in self.supported_currencies:
			frappe.throw(_("Please select another payment method. {0} does not support transactions in currency \"{1}\"").format(self.service_name, currency))

	def build_authorizenet_request(self, **kwargs):
		#Creates an AuthorizeNet Request record to keep params off the url

		data = {
			"doctype": "AuthorizeNet Request",
			"status": "Issued",
		}   
		data.update(kwargs)
		del data["reference_docname"] # have to set it after insert

		request = frappe.get_doc(data)
		request.flags.ignore_permissions = 1
		request.insert()

		# TODO: Why must we save doctype first before setting docname?
		request.reference_docname = kwargs["reference_docname"]
		request.save()
		frappe.db.commit()

		return request

	def get_payment_url(self, **kwargs):
		request = self.build_authorizenet_request(**kwargs)
		url = "./integrations/authorizenet_checkout/{0}"
		result = get_url(url.format(request.get("name" )))
		return result

	def get_settings(self):
		"""settings = frappe._dict({
			"api_login_id": self.api_login_id,
			"api_transaction_key":self.get_password(fieldname='api_transaction_key',raise_exception=False)	
		})"""
		"""settings = frappe._dict({
			"api_login_id": "6M7Hp5u6",
			"api_transaction_key":"8d5MgF9zB6A272df"	
		})"""
		api_login_id=frappe.get_value("Authorizenet Settings","Authorizenet Settings", "api_login_id")
		api_transaction_key= get_decrypted_password('Authorizenet Settings', 'Authorizenet Settings', 'api_transaction_key', False)
		settings=frappe._dict({
			"api_login_id": api_login_id,
			"api_transaction_key":api_transaction_key,
			"sandbox": self.use_sandbox
		})
		return settings                                     

	def process_payment(self):
		# used for feedback about which payment was used
		authorizenet_data = {"error":0}
		#authorizenet_data = []
		 
		data = self.process_data

		settings = self.get_settings()   		
		if not data.get("unittest"): 
				if data.get("name"):
					request = frappe.get_doc("AuthorizeNet Request", data.get("name"))
				else:
					request = self.build_authorizenet_request(**{ \
						key: data[key] for key in \
							('amount', 'currency', 'order_id', 'title', \
							'description', 'payer_email', 'payer_name', \
							'reference_docname', 'reference_doctype') })
					data["name"] = request.get("name")
		else:
			request = frappe.get_doc({"doctype": "AuthorizeNet Request"})  
		
		try: 
			transaction_data = {
				"order": {
					"invoice_number": data["order_id"],
					"description": data["description"]
				},
				"amount": flt(self.process_data.get("amount")),
			} 
			shipment_charges={}                                         
			"""get_reference= frappe.get_doc(request.reference_doctype,request.reference_docname)						                        
			if request.reference_doctype == "Payment Entry":				 
				if len(get_reference.references) == 1:
					inv_ref=get_reference.references 
					ship_charg=frappe.get_doc(inv_ref[0].reference_doctype,inv_ref[0].reference_name)
					if inv_ref[0].reference_doctype == "Sales Invoice":
						shipment_charges= {
							'amount': ship_charg.shipment_amount,
							'name': ship_charg.shipment_name,
							'description':"",
						}
					elif inv_ref[0].reference_doctype == "Sales order":
						shipment_charges= {
							'amount': ship_charg.shipment_cost,
							'name': ship_charg.shipping_service,
							'description':"",
						}
			elif request.reference_doctype == "Payment Request":
				ship_charg=frappe.get_doc(get_reference.reference_doctype,get_reference.reference_name)
				if get_reference.reference_doctype == "Sales Invoice":
					shipment_charges= {
						'amount': ship_charg.shipment_amount,
						'name': ship_charg.shipment_name,
						'description':"",
					}   
				elif get_reference.reference_doctype == 'Sales order': 
					shipment_charges= {       
						'amount': ship_charg.shipment_cost,
						'name': ship_charg.shipping_service,
						'description':"",  
					}"""                                 
			if shipment_charges:
				transaction_data["shipping_and_handling"]=shipment_charges
			transaction_data["line_items"]=get_line_items(request.reference_doctype,request.reference_docname)
			transaction_data["user_fields"]=get_additional_info(request.reference_doctype,request.reference_docname)			
			if frappe.local.request_ip:
					transaction_data.update({
						"extra_options": {
							"customer_ip": frappe.local.request_ip
						}
					})	                    
		
			authorize.Configuration.configure(
				authorize.Environment.TEST if self.use_sandbox else authorize.Environment.PRODUCTION,
				settings.api_login_id,
				settings.api_transaction_key
			)   
			"""authorize.Configuration.configure(
			authorize.Environment.TEST,
			'6M7Hp5u6',
			'8d5MgF9zB6A272df',  
			)   """                                                           
			    
			
			authnet_user = get_authorizenet_user(request.get("payer_name"))   
			authorizenet_profile = self.process_data.get("authorizenet_profile")
			#if user select already saved payment profile then authorizenet_profile is true
			if bool(authorizenet_profile)==False:               
				name_parts = request.get("payer_name").split(' ')
				name_on_card=str(self.card_info.get("name_on_card"))
				billing = self.billing_info	 
				first_name = name_parts[0]
				last_name = " ".join(name_parts[1:]) 
				address=self.billing_info
				address["first_name"] = first_name[:50]
				address["last_name"] = last_name[:50]
				address["company"]=request.get("payer_name")[:50]
				card_store_info = {
					"customer_type": "individual",
					"card_number": self.card_info.get("card_number"),
					"expiration_month": self.card_info.get("exp_month"),
					"expiration_year": self.card_info.get("exp_year"),
					"card_code": self.card_info.get("card_code"),
					"billing": address
				}								
				try:
					if not authnet_user:
						#request.log_action("Creating AUTHNET customer", "Info")
						customer_result = authorize.Customer.create({
								'email': billing.get("auth_email"),
								'description': request.get("payer_name"),
								'customer_type': 'individual',
								'billing': address,
								'credit_card': {
									'card_number': self.card_info.get("card_number"),
									'card_code':self.card_info.get("card_code"),
									'expiration_month': self.card_info.get("exp_month"),
									'expiration_year': self.card_info.get("exp_year")
								}
							})  
						authnet_user=frappe.new_doc("AuthorizeNet Users") 
						authnet_user.authorizenet_id=customer_result.customer_id
						authnet_user.contact=request.get("payer_name")
						authnet_user.email=billing.get("auth_email")      
						authorize_payment_id=customer_result.payment_ids[0]
						
					else:
							print("AUTHORIIIIIZE NET iDDDDDDDDDDDDd")
							print(authnet_user)
							print(authnet_user.get("authorizenet_id"))
							print(card_store_info)
							print("AUTHORIIIIIZE NET iDDDDDDDDDDDDd")

							card_result = authorize.CreditCard.create(authnet_user.get("authorizenet_id"), card_store_info)
							authorize_payment_id=card_result.payment_id	      
					authorizenet_data.update({
						"customer_id":authnet_user.get("authorizenet_id"),
						"payment_id": authorize_payment_id,		
						"name_on_card":name_on_card,	   	
					})  
					authnet_user.append("stored_payments", {
						"doctype": "AuthorizeNet Stored Payment",
						"long_text": "{0}\n{1}\n{2}, {3} {4}".format(
							billing.get("address", ""),
							billing.get("city", ""),
							billing.get("state", ""),
							billing.get("zip", ""),   
							"United States"
						),    
						"address_1": self.billing_info.get("address"),
						"name_on_card":self.card_info.get("name_on_card"),
						"expires": "{0}-{1}-01".format(
							self.card_info.get("exp_year"),
							self.card_info.get("exp_month")),
						"city": self.billing_info.get("city"),
						"state": self.billing_info.get("state"),
						"postal_code": self.billing_info.get("zip"),
						"country": "United States",
						"authorizenet_payment_id":authorize_payment_id,						
						"card_type":get_card_accronym(self.card_info.get("card_number")),
						"card_no": self.card_info.get("card_number")[-4:]
					}) 
								     					                                        
					authnet_user.save()  
					transaction_data.update({
						"customer_id": authnet_user.get("authorizenet_id"),
						"payment_id": authorize_payment_id,										
					})  
				except AuthorizeResponseError as ex:
					card_result = ex.full_response
					authorizenet_data.update({
						"customer_id":"0",
						"payment_id": "0",		
						"name_on_card":"0",
						"error":card_result ,
						"card_no":0, 
						"card_type":0 	
					}) 
					request.log_action(json.dumps(card_result), "Debug")
					request.log_action(str(ex), "Error")
					try:
						# duplicate payment profile
						if card_result["messages"][0]["message"]["code"] == "E00039":
							request.log_action("Duplicate payment profile, ignore", "Error")
						else:
							raise ex
					except:
						raise ex
			else:
				name_on_card=str(authorizenet_profile.get("name_on_card"))
				authorizenet_data.update({
					"customer_id": authnet_user.get("authorizenet_id"),
					"payment_id": authorizenet_profile.get("payment_id"),
					"name_on_card":name_on_card
				})
				
				transaction_data.update({ 
					"email":authorizenet_profile.get("auth_email"),
					"customer_id": authnet_user.get("authorizenet_id"),
					"payment_id": authorizenet_profile.get("payment_id"),
				}) 
				    
			result = authorize.Transaction.sale(transaction_data)		
			request.log_action(json.dumps(result), "Debug")        
			request.transaction_id = result.transaction_response.trans_id						
			request.status = "Captured"    
			authorizenet_data.update({ 
				"card_type":result.transaction_response.account_type,
				"card_no":result.transaction_response.account_number
			})
			
		except AuthorizeInvalidError as iex:
			# log validation errors
			frappe.log_error(frappe.get_traceback(), "AuthorizeInvalidError")
			request.log_action(frappe.get_traceback(), "Error")
			request.status = "Error"
			request.transaction_id="0"            
			error_msg = ""
			errors = []
			if iex.children and len(iex.children) > 0:
				for field_error in iex.children:
					#print(field_error.asdict())
					for error in field_error.asdict().items():
						errors.append(error)
			#error_msg = "\n".join(errors)
			error_msg = str(errors)
			request.error_msg = error_msg
			authorizenet_data.update({
				"customer_id":0,
				"payment_id": "0",		
				"name_on_card":"0",
				"error":error_msg ,
				"card_no":0, 
				"card_type":0 	
			}) 
			#redirect_message=error_msg
			#redirect_to='Error AuthorizeInvalidError'  			
		except AuthorizeResponseError as ex:
			frappe.log_error(frappe.get_traceback(), "AuthorizeResponseError")

			# log authorizenet server response errors
			result = ex.full_response
			request.log_action(json.dumps(result), "Debug")
			request.log_action(str(ex), "Error")
			request.status = "Error"
			request.error_msg = ex.text
			request.transaction_id="0"    
			authorizenet_data.update({
				"customer_id":0,
				"payment_id": "0",		
				"name_on_card":"0",
				"error":ex.text,
				"card_no":0, 
				"card_type":0 	
			}) 
			#redirect_message = str(ex)
			#redirect_to='Error AuthorizeResponseError'
		except Exception as ex:
			frappe.log_error(frappe.get_traceback(), "Exception")

			#log(frappe.get_traceback())
			# any other errors
			request.log_action(frappe.get_traceback(), "Error")
			request.status = "Error"
			request.error_msg = "[UNEXPECTED ERROR]: {0}".format(ex) 
			#redirect_message ="[UNEXPECTED ERROR]: {0}".format(ex) 
			#redirect_to='Error Exception ex'
			authorizenet_data.update({
				"customer_id":0,
				"payment_id": "0",		
				"name_on_card":"0",
				"error":"[UNEXPECTED ERROR]: {0}".format(ex),
				"card_no":0, 
				"card_type":0 	
			}) 
		return request,authorizenet_data
		#return request

	def create_request(self, data):		
		self.process_data = frappe._dict(data)
		# remove sensitive info from being entered into db
		self.card_info = self.process_data.get("card_info")
		self.billing_info = self.process_data.get("billing_info")
		self.shipping_info = self.process_data.get("shipping_info")
		redirect_url = ""		
		#request= self.process_payment() 
		     		
		request,authorizenet_data = self.process_payment()
		
		"""if self.process_data.get('creation'):
    			del self.process_data['creation']
		if self.process_data.get('modified'):
			del self.process_data['modified']
		if self.process_data.get('log'):
			del self.process_data['log']
		if self.process_data.get('card_info'):
    			del self.process_data['card_info']    """               
	 	     
		#if not self.process_data.get("unittest"):
    	#		self.integration_request = create_request_log(self.process_data, "Host", self.service_name)		

		if request.get('status') == "Captured":
    			status = "Completed"
		elif request.get('status') == "Authorized":
			status = "Authorized"
		else:
			status = "Failed"  
	
		#self.integration_request.status = status
		#self.integration_request.save()         
		request.save()              
		if status != "Failed":
			if request.reference_doctype == "Payment Entry": 
					get_pe=frappe.get_doc("Payment Entry",request.reference_docname)   				 
					get_pe.name_on_card=authorizenet_data.get("name_on_card")  
					get_pe.authorizenet_id=authorizenet_data.get("customer_id")
					get_pe.credit_card=authorizenet_data.get("card_no")	
					get_pe.card_type=authorizenet_data.get("card_type")			 
					get_pe.save()  
					#inv_ref=get_pe.references
					#if(len(inv_ref) == 1):			   		 	 		      		 
					#	get_pe.submit()    					 	 		      		 
					#get_pe.submit()            	    					    
			elif request.reference_doctype == "Payment Request":
				auth_req= frappe.get_doc(request.reference_doctype,request.reference_docname)
				sales_invoice=frappe.get_doc(auth_req.reference_doctype,auth_req.reference_name)
				sales_invoice.update({
					"payment_mode":"Credit card",
					"credit_card":authorizenet_data['card_no'],
					"name_on_card":authorizenet_data['name_on_card'], 
					"card_type":authorizenet_data['card_type'],
					"authorizenet_id":authorizenet_data['customer_id'] 
				})
				sales_invoice.save()  		         
				custom_redirect_to = frappe.get_doc(self.process_data.reference_doctype,self.process_data.reference_docname).run_method("on_payment_authorized",status)
		   
		redirect_message="" 
		redirect_url=""

		if request.status == "Captured" or request.status == "Authorized":
			redirect_url = "/integrations/payment-success"
			redirect_message = "Continue Shopping"    
		else:
				redirect_url = "/integrations/payment-failed"
				if request.error_msg:
					redirect_message = "Declined due to:\n" + request.error_msg
				#else:
				#	redirect_message = "Declined:" 

		params = []		
		if redirect_message:
    			params.append(urllib.parse.urlencode({"redirect_message": redirect_message}))
						
		if len(params) > 0:
			redirect_url += "?" + "&".join(params)
		 
		self.process_data = {}
		self.card_info = {}  
		self.billing_info = {}
		self.shipping_info = {}  
		#return authorizenet_data  
		return {                           
			"redirect_to": redirect_url,
			"error": redirect_message if status == "Failed" else None,
			"status": status ,  
			"authorizenet_data": authorizenet_data   
		} 

@frappe.whitelist(allow_guest=True)
def process(options, request_name=None):
	data = {}
	options = json.loads(options) 
	
	if request_name == 'null':
		request_name = None

	if not options.get("unittest"):
		if request_name:
			request = frappe.get_doc("AuthorizeNet Request", request_name).as_dict()
		else:
			request = {}
	else:
		request = {}

	data.update(options)
	data.update(request)    

	data = frappe.get_doc("AuthorizeNet Settings").create_request(data)
	   
	frappe.db.commit()
	return data 
	
@frappe.whitelist()
def test_function():
	return 'testtsts'  

@frappe.whitelist()
def get_service_details():
	return """
		<div>
			<p>    To obtain the API Login ID and Transaction Key:
				<a href="https://support.authorize.net/authkb/index?page=content&id=A405" target="_blank">
					https://support.authorize.net/authkb/index?page=content&id=A405
				</a>
			</p>
			<p> Steps to configure Service:</p>
			<ol>
				<li>
					Log into the Merchant Interface at https://account.authorize.net.
				</li>
				<br>
				<li>
					Click <strong>Account</strong> from the main toolbar.
				</li>
				<br>
				<li>
					Click <strong>Settings</strong> in the main left-side menu.
				</li>
				<br>
				<li>
					Click <strong>API Credentials & Keys.</strong>
				</li>
				<br>
				<li>
					Enter your <strong>Secret Answer.</strong>
				</li>
				<br>
				<li>
					Select <strong>New Transaction Key.</strong>
				</li>
				<br>
				<li>
					Input API Credentials in <a href="/desk#Form/AuthorizeNet%20Settings">AuthorizeNet Settings</a>
				</li>
				<br>
			</ol>
			<p>
				<strong>Note:</strong> When obtaining a new Transaction Key, you may choose to disable the old Transaction Key by clicking the box titled, <strong>Disable Old Transaction Key Immediately</strong>. You may want to do this if you suspect your previous Transaction Key is being used fraudulently.
				Click Submit to continue. Your new Transaction Key is displayed.
				If the <strong>Disable Old Transaction Key Immediately</strong> box is not checked, the old Transaction Key will automatically expire in 24 hours. When the box is checked, the Transaction Key expires immediately.
			</p>
			<p>
				Be sure to store the Transaction Key in a very safe place. Do not share it with anyone, as it is used to protect your transactions.
			</p>
			<p>
				The system-generated Transaction Key is similar to a password and is used to authenticate requests submitted to the gateway. If a request cannot be authenticated using the Transaction Key, the request is rejected. You may generate a new Transaction Key as often as needed.
			</p>   
		</div>
	"""
