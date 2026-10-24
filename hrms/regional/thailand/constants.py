"""What Thai payroll needs on the HRMS and ERPNext masters, laid out as sections of their own.

Custom fields only: the payroll formulas, reports and approvals of a company stay in the app that owns them. A
salary structure formula reads `provident_fund_rate` from the employee's Salary Structure Assignment, so the
members of a provident fund are dated; the national ID and social security fields hold what the SSO 1-10 form and
the password of a salary slip need.
"""

# What a Salary Component is for a Thai filing: PND1 / 50 Tawi, SSO 1-10, provident fund report.
REGULAR_WAGE = "Regular Wage"
INCOME_TAX = "Income Tax (PND1)"
SSO_EMPLOYEE = "Social Security (Employee)"
SSO_EMPLOYER = "Social Security (Employer)"
PVD_EMPLOYEE = "Provident Fund (Employee)"
PVD_EMPLOYER = "Provident Fund (Employer)"
STATUTORY_TYPES = (REGULAR_WAGE, INCOME_TAX, SSO_EMPLOYEE, SSO_EMPLOYER, PVD_EMPLOYEE, PVD_EMPLOYER)

# The payroll fields only HR Manager and Payroll Manager may read or write (permlevel 1 of Employee).
PAYROLL_PERMLEVEL = 1
PAYROLL_ROLES = ("HR Manager", "Payroll Manager")

# Employee numbers: the Buddhist-era year, the month and a running number of the month, as in 6810001 (YY-BE 68,
# month 10, number 001). YY-BE and YYYY-BE are naming series parts of hrms.regional.thailand.naming.
EMPLOYEE_SERIES = "YY-BE.MM.###"

# Thai salutations, next to the English ones of ERPNext (Mr, Mrs, Ms...).
THAI_SALUTATIONS = ("นาย", "นาง", "นางสาว")

# (doctype, fieldname, property, value, property type)
PROPERTY_SETTERS = (
	("Employee", "naming_series", "options", EMPLOYEE_SERIES, "Text"),
	# the signature is made in a popup (Sign / Re-sign button), so the field itself only shows it
	("Employee", "signature", "read_only", 1, "Check"),
)

HRMS_THAILAND_CUSTOM_FIELDS = {
	# Personal Details tab, under the passport: a section of its own for the Thai identity and social security.
	"Employee": [
		# Overview tab, next to the Thai name (salutation, first, middle, last, full name): the same in English.
		{
			"fieldname": "column_break_name_en",
			"fieldtype": "Column Break",
			"insert_after": "employee_name",
		},
		{
			"fieldname": "salutation_en",
			"fieldtype": "Link",
			"label": "Salutation EN",
			"options": "Salutation",
			"insert_after": "column_break_name_en",
		},
		{
			"fieldname": "first_name_en",
			"fieldtype": "Data",
			"label": "First Name EN",
			"insert_after": "salutation_en",
		},
		{
			"fieldname": "middle_name_en",
			"fieldtype": "Data",
			"label": "Middle Name EN",
			"insert_after": "first_name_en",
		},
		{
			"fieldname": "last_name_en",
			"fieldtype": "Data",
			"label": "Last Name EN",
			"insert_after": "middle_name_en",
		},
		{
			"fieldname": "full_name_en",
			"fieldtype": "Data",
			"label": "Full Name EN",
			"insert_after": "last_name_en",
			"read_only": 1,
			"no_copy": 1,
		},
		# User Details: the Sign / Re-sign button opens the signature pad (public/js/thailand/employee.js).
		{
			"fieldname": "sign_button",
			"fieldtype": "Button",
			"label": "Sign",
			"insert_after": "signature",
		},
		{
			"fieldname": "thai_identity_section",
			"fieldtype": "Section Break",
			"label": "National ID & Social Security (Thailand)",
			"insert_after": "place_of_issue",
		},
		{
			"fieldname": "national_id_number",
			"fieldtype": "Data",
			"label": "National ID Number",
			"insert_after": "thai_identity_section",
			"permlevel": PAYROLL_PERMLEVEL,
			"no_copy": 1,
			"description": "Opens the password-protected Salary Slip PDF. Only HR and Payroll can read it.",
		},
		{
			"fieldname": "social_security_id",
			"fieldtype": "Data",
			"label": "Social Security ID",
			"insert_after": "national_id_number",
			"permlevel": PAYROLL_PERMLEVEL,
			"no_copy": 1,
			"description": "The ID on the SSO 1-10 form. Leave blank when it is the National ID Number.",
		},
		{
			"fieldname": "thai_identity_column",
			"fieldtype": "Column Break",
			"insert_after": "social_security_id",
		},
		{
			"fieldname": "social_security_eligible",
			"fieldtype": "Check",
			"label": "Social Security Eligible",
			"insert_after": "thai_identity_column",
			"description": "Ticked: the salary structure takes the employee's and the employer's social security.",
		},
	],
	# The membership of a provident fund belongs to the assignment, so it has a start date and a history.
	"Salary Structure Assignment": [
		{
			"fieldname": "provident_fund_section",
			"fieldtype": "Section Break",
			"label": "Provident Fund (Thailand)",
			"insert_after": "leave_encashment_amount_per_day",
		},
		{
			"fieldname": "provident_fund_rate",
			"fieldtype": "Percent",
			"label": "Provident Fund Rate (%)",
			"insert_after": "provident_fund_section",
			"description": "Employee savings rate. Leave blank or 0 when the employee is not a member.",
		},
		{
			"fieldname": "provident_fund_column",
			"fieldtype": "Column Break",
			"insert_after": "provident_fund_rate",
		},
		{
			"fieldname": "provident_fund_employer_rate",
			"fieldtype": "Percent",
			"label": "Provident Fund Employer Rate (%)",
			"insert_after": "provident_fund_column",
			"description": "Employer contribution rate. Leave blank when it is the same as the employee's rate.",
		},
	],
	"Salary Component": [
		{
			"fieldname": "thai_statutory_type",
			"fieldtype": "Select",
			"label": "Thai Statutory Type",
			"options": "\n" + "\n".join(STATUTORY_TYPES),
			"insert_after": "type",
			"description": "Which Thai filing this component feeds: PND1 / 50 Tawi, SSO 1-10, provident fund report",
		},
	],
	# HR & Payroll tab, after the HR settings: the employer's numbers on the SSO 1-10 form.
	"Company": [
		{
			"fieldname": "social_security_section",
			"fieldtype": "Section Break",
			"label": "Social Security (Thailand)",
			"insert_after": "skills",
		},
		{
			"fieldname": "social_security_account_no",
			"fieldtype": "Data",
			"label": "Social Security Employer Account No",
			"insert_after": "social_security_section",
			"description": "เลขที่บัญชีนายจ้าง (10 digits) on the SSO 1-10 form",
		},
		{
			"fieldname": "social_security_column",
			"fieldtype": "Column Break",
			"insert_after": "social_security_account_no",
		},
		{
			"fieldname": "social_security_branch_no",
			"fieldtype": "Data",
			"label": "Social Security Branch No",
			"default": "000000",
			"insert_after": "social_security_column",
			"description": "ลำดับที่สาขา (6 digits, 000000 = head office) on the SSO 1-10 form",
		},
	],
}
