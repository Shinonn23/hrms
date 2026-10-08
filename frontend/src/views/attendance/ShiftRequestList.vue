<template>
	<ion-page>
		<ListView
			doctype="Shift Request"
			:pageTitle="__('Shift Request History')"
			:tabButtons="TAB_BUTTONS"
			:fields="SHIFT_REQUEST_FIELDS"
			:filterConfig="FILTER_CONFIG"
		/>
	</ion-page>
</template>

<script setup>
import { inject } from "vue"
import { IonPage } from "@ionic/vue"
import ListView from "@/components/ListView.vue"

const __ = inject("$translate")
const TAB_BUTTONS = ["My Requests", "Team Requests"]
const SHIFT_REQUEST_FIELDS = [
	"name",
	"employee",
	"employee_name",
	"shift_type",
	"from_date",
	"to_date",
	"docstatus",
]
const FILTER_CONFIG = [
	{
		fieldname: "shift_type",
		fieldtype: "Link",
		label: __("Shift Type"),
		options: "Shift Type",
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
	{ fieldname: "from_date", fieldtype: "Date", label: __("From Date") },
	{ fieldname: "to_date", fieldtype: "Date", label: __("To Date") },
]
</script>
