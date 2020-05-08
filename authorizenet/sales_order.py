import frappe, json


@frappe.whitelist()
def category_count(name, counts):
    data = json.loads(counts)
    print(data)
    for idx,i in enumerate(data):
        get_item_group_records = frappe.db.sql(""" SELECT * FROM `tabItem Group Count` WHERE parent=%s and category=%s""", (name, i['item_group']))
        if len(get_item_group_records) == 0:
            frappe.get_doc({
                "doctype": "Item Group Count",
                "parent": name,
                "parenttype": "Sales Order",
                "parentfield": "category_counts",
                "category": i['item_group'],
                "count": i['count'],
                "idx": idx
            }).insert()
    return "success"