from __future__ import unicode_literals
import frappe
from frappe import _, session

import authorize   

def _range(a,b):
	return [x for x in range(a,b)]

CARDS = {
	'AMEX':         [34, 37],
	'CHINAUP':      [62, 88],
	'DinersClub':   _range(300, 305)+[309, 36, 54, 55]+_range(38, 39),
	'DISCOVER':     [6011, 65] + _range(622126, 622925) + _range(644, 649),
	'JCB':          _range(3528, 3589),
	'LASER':        [6304, 6706, 6771, 6709],
	'MAESTRO':      [5018, 5020, 5038, 5612, 5893, 6304, 6759, 6761, 6762, 6763, 604, 6390],
	'DANKORT':      [5019],
	'MASTERCARD':   _range(50, 55),
	'VISA':         [4],
	'VISAELECTRON': [4026, 417500, 4405, 4508, 4844, 4913, 4917]  
}

def get_contact(contact_name = None):		
		user = session.user
		contact = None
		#if isinstance(user, unicode):
		user = frappe.get_doc("User", user)

		if not contact_name:
			contact_names = frappe.get_all("Contact", fields=["name"], filters={
				"user": user.name
			})
			if not contact_names or len(contact_names) == 0:
				contact_names = frappe.get_all("Contact", fields=["name"], filters={
					"email_id": user.email
				})

			if contact_names and len(contact_names) > 0:
				contact_name = contact_names[0].get("name")

		if contact_name:
			contact = frappe.get_doc("Contact", contact_name)

		return contact

def get_authorizenet_user(contact):
	authnet_user = None
	try:   
		authnet_user_ = frappe.get_list("AuthorizeNet Users", fields=["name"], filters={"contact": contact}, as_list=1)
		if authnet_user_:
			authnet_user_name = authnet_user_[0][0]
			authnet_user = frappe.get_doc("AuthorizeNet Users", authnet_user_name)
	except:
		authnet_user = None
	return authnet_user  
	
def get_card_accronym(number):
	card_name = ''
	card_match_size = 0
	for name, values in CARDS.items():
		for digits in values:
			digits = str(digits)
			if number.startswith(digits):
				if len(digits) > card_match_size:
					card_match_size = len(digits)
					card_name = name

	return card_name

def authnet_address(fields):
	address = {}

	if fields is None:
		return address

	if fields.get("first_name"):
		address["first_name"] = fields.get("first_name")[:50]
	if fields.get("last_name"):
		address["last_name"] = fields.get("last_name")[:50]
	if fields.get("company"):
		address["company"] = fields.get("company")[:50]
	if fields.get("address_1"):
		address["address"] = "%s %s" % (fields.get("address_1"), fields.get("address_2", ""))
		address["address"] = address["address"][:60]
	if fields.get("city"):
		address["city"] = fields.get("city", "")[:40]
	if fields.get("state"):
		address["state"] = fields.get("state", "")[:40]
	if fields.get("pincode"):
		address["zip"] = fields.get("pincode")[:20]
	if fields.get("country"):
		address["country"] = fields.get("country", "")[:60]
	if fields.get("phone_number"):
		address["phone_number"] = fields.get("phone_number")[:25]

	return address

@frappe.whitelist()
def test_function():   
	authnet_user = None		
	contact = get_contact()
	if contact:
		authnet_user_name = frappe.get_list("Customer", fields=["name"], filters={"customer_primary_contact": contact.name}, as_list=1)
		if len(authnet_user_name) > 0:
			authnet_user_name = authnet_user_name[0][0]
			authnet_user = frappe.get_doc("Customer", authnet_user_name)
	return authnet_user

def get_customer(contact):   
	authnet_user = None		
	#contact = get_contact()
	if contact:
		authnet_user = frappe.get_doc("Customer", contact)
		"""if len(authnet_user_name) > 0:
			authnet_user = authnet_user_name[0][0]
			#authnet_user = frappe.get_doc("Customer", authnet_user_name)"""
	return authnet_user

"""def get_primary_address(address):
		authnet_user_address=None
		if address:					
			authnet_address_title = frappe.db.get_all("Address", fields=["name"], filters={"name": address})
			if (len (authnet_address_title)>0):		
				authnet_user_address = frappe.get_doc("Address", authnet_address_title[0]['name'])
		return authnet_user_address  """

def get_primary_address(contact,payment_id): 
		authnet_user_address=[]
		try:   
			authnet_user_ = frappe.get_list("AuthorizeNet Users", fields=["name"], filters={"contact": contact}, as_list=1)
			if authnet_user_:
				authnet_user_name = authnet_user_[0][0]
				authnet_user = frappe.get_doc("AuthorizeNet Users", authnet_user_name)				
				for add in authnet_user.stored_payments:					
						if(add.authorizenet_payment_id==payment_id):
									authnet_user_address={
										"address":add.address_1,
										"city":add.city,
										"state":add.state,
										"zip":add.postal_code,
										"country":"USA"
									}   								
		except:
			authnet_user_address=[]
		return authnet_user_address  

"""@frappe.whitelist()
def get_primary_address():
		address=None	
		contact = get_contact()
		if contact:
			authnet_user_name = frappe.get_list("Customer", fields=["name"], filters={"customer_primary_contact": contact.name}, as_list=1)
			if len(authnet_user_name) > 0:
					authnet_user_name = authnet_user_name[0][0]
					authnet_user = frappe.get_doc("Customer", authnet_user_name)
					address=authnet_user.customer_primary_address
					authnet_address_title = frappe.get_list("Address", fields=["name"], filters={"name": address}, as_list=1)
					address=authnet_address_title[0][0]
					authnet_user_address = frappe.get_doc("Address", address)
		return authnet_user_address"""

@frappe.whitelist()
def get_shipping_address(reference_doctype,reference_docname):
	shipping_address=[]
	auth_req= frappe.get_doc(reference_doctype, reference_docname)
	sales_invoice=frappe.get_doc(auth_req.reference_doctype,auth_req.reference_name)
	_address=frappe.get_doc("Address", sales_invoice.customer_address)		
	shipping_address={
		'first_name': _address.address_title,
		'last_name': '',
		'company': '',
		'address': _address.address_line1,
		'city': _address.city,
		'state': _address.state, 
		'zip': _address.pincode,
		'country': _address.country, 
	}  
	return shipping_address 
	
@frappe.whitelist()
def get_additional_info(reference_doctype,reference_docname):
	add_info_detail=[]	
	auth_req= frappe.get_doc(reference_doctype, reference_docname)
	if reference_doctype == 'Payment Entry':
		inv_ref=auth_req.references
		if(len(inv_ref) == 1):
			sales_invoice=frappe.get_doc(inv_ref[0].reference_doctype,inv_ref[0].reference_name)
			if(len(sales_invoice.items)<30):  
				add_info={
						'name': 'Warning', 
						'value': 'Line items more than 30 are not shown here due to limitation'
					}
				add_info_detail.append(add_info) 
			for item in sales_invoice.items:
				if(item.qty > 99 or item.rate > 99):
					add_info={
						'name': 'Warning', 
						'value': 'Quantity or Unit Price exceeding 99 has been moved to description coloumn due to limitation'
					}
					add_info_detail.append(add_info)
					break 
	elif(reference_doctype == 'Payment Request'):
		sales_invoice=frappe.get_doc(auth_req.reference_doctype,auth_req.reference_name)		
		for item in sales_invoice.items:
			if(item.qty > 99 or item.rate > 99):
				add_info={
					'name': 'Warning', 
					'value': 'Quantity or Unit Price exceeding 99 has been moved to description coloumn due to limitation'
				}
				add_info_detail.append(add_info)
	return add_info_detail 

@frappe.whitelist()
def get_line_items(reference_doctype,reference_docname):
	lst_line_item=[]
	auth_req= frappe.get_doc(reference_doctype, reference_docname)
	#auth_req= frappe.get_doc('Payment Entry', 'PE-00066')
	if(reference_doctype == 'Payment Entry'):
		inv_ref=auth_req.references
		if(len(inv_ref) == 1):
				sales_invoice=frappe.get_doc(inv_ref[0].reference_doctype,inv_ref[0].reference_name)
				#return sales_invoice
				item_count=1
				for item in sales_invoice.items:
					if(item_count<31):
						if(item.qty > 99 or item.rate > 99):
							#(Qty:999, Price:999, Total:999)
							val=int(item.qty)*int(item.rate)
							ss="Qty:"+str(item.qty)+",Price:"+str(item.rate)+",Total:"+str(val)
							line_items={
									"item_id":item.item_code[:31],
									"name": item.item_name[:31],
									"description":ss[:224],
									"quantity":1,
									"unit_price":1,   
								}    
							lst_line_item.append(line_items)
						else:  
							line_items={
									"item_id":item.item_code[:31],
									"name": item.item_name[:31],
									"description":item.description[:224],
									"quantity":item.qty,
									"unit_price":item.rate,   
								}
							lst_line_item.append(line_items)
					item_count=item_count+1				
	elif(reference_doctype == 'Payment Request'):
		sales_invoice=frappe.get_doc(auth_req.reference_doctype,auth_req.reference_name)
		for item in sales_invoice.items:
			if(item.qty> 99 or item.rate > 99):
				#(Qty:999, Price:999, Total:999)
				val=int(item.qty)*int(item.rate)
				ss="Qty:"+str(item.qty)+",Price:"+str(item.rate)+",Total:"+str(val)
				line_items={
						"item_id":item.item_code[:31],
						"name": item.item_name[:31],
						"description":ss[:224],
						"quantity":1,
						"unit_price":1,   
					}    
				lst_line_item.append(line_items)
			else:  
				line_items={
						"item_id":item.item_code[:31],
						"name": item.item_name[:31],
						"description":item.description[:224],
						"quantity":item.qty,
						"unit_price":item.rate,   
					}
				lst_line_item.append(line_items)
	return lst_line_item

			
"""@frappe.whitelist()
def get_shipment_charges(reference_doctype,reference_docname):
			shipping_and_handling=None
			auth_req= frappe.get_doc(reference_doctype, reference_docname)
			ship_charg=frappe.get_doc(auth_req.reference_doctype,auth_req.reference_name)
			#if (ship_charg.shipment_amount and ship_charg.shipment_name):				
			shipping_and_handling= {
					'amount': ship_charg.shipment_amount,
					'name': ship_charg.shipment_name,
					'description':"",
			}
			 
			return shipping_and_handling
			
@frappe.whitelist()
def get_tax_charges(reference_doctype,reference_docname):
			tax=None
			auth_req= frappe.get_doc(reference_doctype, reference_docname)
			total_tax=frappe.get_doc(auth_req.reference_doctype,auth_req.reference_name)
			if (total_tax.total_taxes_and_charges):				
					tax={ 
						'amount': total_tax.total_taxes_and_charges,
						'name': 'Double Taxation Tax',
						'description': 'Another tax for paying double tax',
					}
			return tax
		
"""


@frappe.whitelist()
def submit_pe(payment_entry):
	pe = frappe.get_doc("Payment Entry",payment_entry)
	pe.submit()


@frappe.whitelist()
def test_authorizenet():
	from frappe.utils.password import get_decrypted_password

	print(get_decrypted_password('AuthorizeNet Settings', 'AuthorizeNet Settings', 'api_transaction_key', False))
	print(frappe.get_value("AuthorizeNet Settings","AuthorizeNet Settings", "api_login_id"))