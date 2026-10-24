import json

import click

import frappe
from frappe.commands import pass_context
from frappe.exceptions import SiteNotSpecifiedError


@click.command("sync-employee-series")
@click.option("--apply", "apply", is_flag=True, help="Raise the counters; without it only the plan is shown.")
@click.option("--series", help="The series to check, as in the Series field. Defaults to the Employee's.")
@click.option(
	"--all-months",
	"all_prefixes",
	is_flag=True,
	help="Also look at the prefixes (months) that have no counter yet; old ones have nothing to repair.",
)
@pass_context
def sync_employee_series(context, apply, series, all_prefixes):
	"""Move the running number of the Employee series up to the highest number that exists (after a rename)."""
	from hrms.regional.thailand.series import sync

	if not context.sites:
		raise SiteNotSpecifiedError
	if len(context.sites) != 1:
		raise click.ClickException("Select exactly one site with --site.")
	frappe.init(context.sites[0])
	try:
		frappe.connect()
		result = sync(series, apply, all_prefixes)
		click.echo(json.dumps({"site": context.sites[0], **result}, ensure_ascii=False))
	finally:
		frappe.destroy()


commands = [sync_employee_series]
