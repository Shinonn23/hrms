<template>
	<ion-page>
		<ListView
			doctype="Expense Claim"
			:pageTitle="__('Claim History')"
			:tabButtons="TAB_BUTTONS"
			:fields="EXPENSE_CLAIM_FIELDS"
			groupBy="`tabExpense Claim`.name"
			:filterConfig="FILTER_CONFIG"
		/>
	</ion-page>
</template>

<script setup>
import { IonPage } from "@ionic/vue"
import ListView from "@/components/ListView.vue"


const TAB_BUTTONS = ["My Claims", "Team Claims"] // __("My Claims"), __("Team Claims")
const EXPENSE_CLAIM_FIELDS = [
	"`tabExpense Claim`.name",
	"`tabExpense Claim`.employee",
	"`tabExpense Claim`.employee_name",
	"`tabExpense Claim`.currency",
	"`tabExpense Claim`.status",
	"`tabExpense Claim`.total_claimed_amount",
	"`tabExpense Claim`.posting_date",
	"`tabExpense Claim`.company",
	"`tabExpense Claim Detail`.expense_type",
	{"COUNT": "`tabExpense Claim Detail`.expense_type", "as":"total_expenses"}
]

const FILTER_CONFIG = [
	{
		fieldname: "status",
		fieldtype: "Select",
		label: __("Status"),
		options: ["Draft", "Paid", "Partially Paid", "Unpaid", "Submitted", "Cancelled"],
	},
	{
		fieldname: "employee",
		fieldtype: "Link",
		label: __("Employee"),
		options: "Employee",
	},
	{
		fieldname: "department",
		fieldtype: "Link",
		label: __("Department"),
		options: "Department",
	},
	{ fieldname: "posting_date", fieldtype: "Date", label: __("Posting Date") },
]
</script>
