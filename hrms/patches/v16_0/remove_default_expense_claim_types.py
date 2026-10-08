import frappe


DEFAULT_EXPENSE_CLAIM_TYPES = (
	"Calls",
	"Food",
	"Gasoline",
	"Medical",
	"Others",
	"Telephone",
	"Travel",
	"Traveling",
	"ค่าที่พัก",
	"à¸„à¹ˆà¸²à¸—à¸µà¹ˆà¸žà¸±à¸",
)


def execute():
	for expense_type in DEFAULT_EXPENSE_CLAIM_TYPES:
		if not frappe.db.exists("Expense Claim Type", expense_type):
			continue

		try:
			frappe.delete_doc("Expense Claim Type", expense_type, ignore_permissions=True)
		except frappe.LinkExistsError:
			print(f"Keeping Expense Claim Type {expense_type!r}: it is linked to existing documents")
