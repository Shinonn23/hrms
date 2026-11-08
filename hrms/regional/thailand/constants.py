"""What Thai payroll needs on the HRMS and ERPNext masters.

The fields are in the DocType JSON of the forks (Siwat, 8 Nov 2026; they used to be Custom Fields made here): Employee
and Company in the ERPNext fork (`erpnext/setup/doctype/employee`, `.../company`), Salary Structure Assignment and
Salary Component in this one. The payroll formulas, reports and approvals of a company stay in the app that owns them.
A salary structure formula reads `provident_fund_rate` from the employee's Salary Structure Assignment, so the
members of a provident fund are dated; the national ID and social security fields hold what the SSO 1-10 form and
the password of a salary slip need. This file keeps the names those fields use.
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

# Employee numbers: the Buddhist-era year and the month of the Date of Joining and a running number of that month, as
# in 6810001 (YY-BE 68, month 10, number 001). The parts are those of hrms.regional.thailand.naming.
EMPLOYEE_SERIES = "YY-BE.MM-BE.###"

# Thai salutations, next to the English ones of ERPNext (Mr, Mrs, Ms...).
THAI_SALUTATIONS = ("นาย", "นาง", "นางสาว")

# (doctype, fieldname, property, value, property type)
PROPERTY_SETTERS = (
	("Employee", "naming_series", "options", EMPLOYEE_SERIES, "Text"),
	# the signature is made in a popup (Sign / Re-sign button), so the field itself only shows it
	("Employee", "signature", "read_only", 1, "Check"),
)
