# -*- coding: utf-8 -*-
# Copyright (c) 2015, DigiThinkIT, Inc. and contributors
# For license information, please see license.txt
from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import authorize
import json
from authorize import AuthorizeResponseError, AuthorizeInvalidError
from frappe import _, _dict
from frappe.utils import get_url, call_hook_method, flt
from frappe.integrations.utils import create_request_log, create_payment_gateway
from datetime import datetime
import urllib
from frappe.utils.password import get_decrypted_password
class AuthorizeNetUsers(Document):
	pass
@frappe.whitelist()
def test_user1():
    	return "ok"
@frappe.whitelist()
def test_user(customer_detail):
							card_number=""
							card_code=""
							expiration_month=""
							expiration_year=""
							customer_name=""
							customer_group=""
							customer_type=""
							email_id=""
							authorize_id=""
							payment_id = ""
							shipping_id = ""
							customer_info=""
							account_type=""
							routing_number=""
							account_number=""
							name_on_account=""
							bank_name=""
							echeck_type=""
							credit_card={}
							bank_account={}
							error_msg = ""
							errors = []
							#process_data = frappe._dict(customer_detail)
							#data = process_data
							request = frappe.get_doc({"doctype": "AuthorizeNet Request"})
							request.flags.ignore_permissions = 1
							log_level=frappe.get_value("Authorizenet Settings","Authorizenet Settings", "log_level")
							request.max_log_level(log_level) 							
							i= json.loads(customer_detail)
							if "customer_id" in i:
								authorize_id=i['customer_id']
							if "payment_id" in i:
								payment_id=i['payment_id']
							if "shipping_id" in i:
								shipping_id=i['shipping_id']
							addr_list={}
							Shipping={}
							Billing={}
							api_login_id=frappe.get_value("AuthorizeNet Settings","AuthorizeNet Settings", "api_login_id")
							if_sandbox=frappe.get_value("AuthorizeNet Settings","AuthorizeNet Settings", "use_sandbox")
							api_transaction_key= get_decrypted_password('AuthorizeNet Settings', 'AuthorizeNet Settings', 'api_transaction_key', False)
							if '__onload' in i:    							 
									addr_list=i['__onload']['addr_list']
							if 'customer_name' in i:
									customer_name=i['customer_name']
							if 'card_number' in i:
									card_number=i['card_number']
							if 'card_code' in i:
									card_code=i['card_code']
							if 'expiration_month' in i:
									expiration_month=i['expiration_month']
							if 'expiration_year' in i:
									expiration_year=i['expiration_year']
							if 'account_type' in i:
    								account_type=i['account_type']
							if 'routing_number' in i:
    								routing_number=i['routing_number']
							if 'account_number' in i:
    								account_number=i['account_number']
							if 'name_on_account' in i:
    								name_on_account=i['name_on_account']
							if 'bank_name' in i:
    								bank_name=i['bank_name']
							if 'echeck_type' in i:
    								echeck_type=i['echeck_type']	
							if 'customer_group'	in i:
									customer_group=i['customer_group']
							if 'customer_type' in i:
										if(i['customer_type']=='individual'):
												customer_type='individual'
										elif(i['customer_type']=='Company'):
												customer_type='business'    										
							if 'email_id' in i:
									email_id=i['email_id']
							if(card_number!='' and card_code!='' and expiration_month!='' and expiration_year!=''):
									credit_card={
										'card_number': card_number,
										'card_code': card_code,
										'expiration_month': expiration_month,
										'expiration_year': expiration_year,
									}
							if(account_type!='' and routing_number!='' and account_number!='' and name_on_account!='' and bank_name!='' and echeck_type!=''):
    								bank_account={
										'account_type': account_type,
										'routing_number': routing_number,
										'account_number':account_number,
										'name_on_account': name_on_account,
										'bank_name': bank_name,
										'echeck_type':echeck_type
									}
							customer_info={
								'email': email_id,
								'description': customer_group,
								'customer_type': customer_type,																					
							}
							
							if (len(addr_list)>0):
											j=i['__onload']
											for item in j['addr_list']:
												address_type=item['address_type']
												city=item['city']
												state=item['state']
												country=item['country']
												fax=item['fax']
												address=item['address_line1']
												phone=item['phone']
												if(address_type=='Shipping'):   										
													Shipping={
														'first_name':customer_name,
														'company': 'Robotron Studios',
														'address': address,
														'city': city,
														'state': state,
														'country': country,
														'phone_number': phone,
														'fax_number': fax,
													}
												elif(address_type=='Billing'):
													Billing={
														'first_name':customer_name,
														'company': 'Robotron Studios',
														'address': address,
														'city': city,
														'state': state,
														'country': country,
														'phone_number':phone,
														'fax_number': fax,
													}										
							if(authorize_id=="0"):
										try:
												print("aksdakjsld")
												if(bool(Billing)):
														customer_info.update({"billing":Billing})
												if(bool(Shipping)):
														customer_info.update({"shipping":Shipping})
												if(bool(credit_card)):
														customer_info.update({"credit_card":credit_card})
												if(bool(bank_account)):
														customer_info.update({"bank_account":bank_account})

												authorize.Configuration.configure(							
														authorize.Environment.TEST if(if_sandbox)  else authorize.Environment.PRODUCTION,
														api_login_id,
														api_transaction_key   
												)
												result = authorize.Customer.create(customer_info)
												customer={
														"customer_id":result.customer_id,
														"status":"Completed",
														"payment_id":0,
														"shipping_id":0													
												}  
												if(result.payment_ids): 
													customer["payment_id"]=result.payment_ids[0]
												if(result.address_ids):
													customer["shipping_id"]=result.address_ids[0]
												request.status='Completed'
												return customer
										except AuthorizeInvalidError as iex:
												print("aksdakjsld1111")
												frappe.log_error(frappe.get_traceback(), "AuthorizeInvalidError 000")

												request.log_action(frappe.get_traceback(), "Error")
												request.status = "Error Insert"
												if iex.children and len(iex.children) > 0:
													for field_error in iex.children:
														print(field_error.asdict())
														for field_name, error in field_error.asdict().items():
															errors.append(error) 
															error_msg = "\n".join(errors)
															request.error_msg = error_msg
												return request      
										except AuthorizeResponseError as ex:
												print("aksdakjsld22222")
												frappe.log_error(frappe.get_traceback(), "AuthorizeResponseError 000")

												# log authorizenet server response errors
												result = ex.full_response
												request.log_action(json.dumps(result), "Debug")
												request.log_action(str(ex), "Error")
												request.status = "Error insert"
												request.error_msg = ex.text
												redirect_message = str(ex)
												return request       
										except Exception as ex:
												print("aksdakjsld3333")
												frappe.log_error(frappe.get_traceback(), "Exception 000")

												# any other errors
												request.log_action(frappe.get_traceback(), "Error")
												request.status = "Error insert"
												request.error_msg = "[UNEXPECTED ERROR]: {0}".format(ex)
												return request 					
							else:    
											try:
													if(bool(Billing) and bool(credit_card)):
    														credit_card.update({"billing":Billing})
													if(bool(Billing) and bool(bank_account)):
    														bank_account.update({"billing":Billing})
													authorize.Configuration.configure(							
															authorize.Environment.TEST if(if_sandbox)  else authorize.Environment.PRODUCTION,
															api_login_id,
															'84CtWqm73UP8Pg45'   
													)
													result_shipping={}
													result_payment={}
													if(bool(Shipping) and shipping_id=="0"):
														result_shipping=authorize.Address.create(authorize_id,Shipping)
													elif(bool(Shipping) and shipping_id!="0"):	
															result_shipping = authorize.Address.update(authorize_id,shipping_id,Shipping)													
													if(bool(credit_card) and payment_id=="0"):
    														result_payment=authorize.CreditCard.create(authorize_id,credit_card)
													elif(bool(credit_card) and payment_id!="0"):
    														result_payment=authorize.CreditCard.update(authorize_id,payment_id,credit_card)
													if(bool(bank_account) and payment_id=="0"):
    														result_payment=authorize.BankAccount.create(authorize_id,bank_account)
													elif(bool(bank_account) and payment_id!="0"):
    														result_payment=authorize.BankAccount.update(authorize_id,payment_id,bank_account)
    														
													result_customer = authorize.Customer.update(authorize_id,customer_info)
													customer={     
														"payment_id":0,
														"shipping_id":0,
														"status":'Completed'													
													}  
													if 'payment_id' in result_payment:
															customer["payment_id"]=result_payment.payment_id
													if 'address_id' in result_shipping:
															customer["shipping_id"]=result_shipping.address_id  
													return customer   
											except AuthorizeInvalidError as iex:
												frappe.log_error(frappe.get_traceback(), "AuthorizeInvalidError")
												request.log_action(frappe.get_traceback(), "Error")
												request.status = "Error update"
												if iex.children and len(iex.children) > 0:
													for field_error in iex.children:
														print(field_error.asdict())
														for field_name, error in field_error.asdict().items():
															errors.append(error)
															error_msg = "\n".join(errors)
															request.error_msg = error_msg
											except AuthorizeResponseError as ex:
													frappe.log_error(frappe.get_traceback(),"AuthorizeResponseError")  # log authorizenet server response errors
													result = ex.full_response
													request.log_action(json.dumps(result), "Debug")
													request.log_action(str(ex), "Error")
													request.status = "Error"
													request.error_msg = ex.text
													redirect_message = str(ex)
													return request
											except Exception as ex:
													frappe.log_error(frappe.get_traceback(),"Exception")  # log authorizenet server response errors

													# any other errors
													request.log_action(frappe.get_traceback(), "Error")
													request.status = "Error"
													authorize_id
													request.error_msg = "[UNEXPECTED ERROR]: {0}".format(ex)
													return request