<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<FormView
				v-if="formFields.data"
				doctype="Shift Request"
				v-model="shiftRequest"
				:isSubmittable="true"
				:fields="formFields.data"
				:id="props.id"
				@validateForm="validateForm"
			/>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonPage, IonContent } from "@ionic/vue"
import { createResource } from "frappe-ui"
import { ref, watch, inject } from "vue"

import FormView from "@/components/FormView.vue"

const employee = inject("$employee")

const props = defineProps({
	id: {
		type: String,
		required: false,
	},
})

// reactive object to store form data
const shiftRequest = ref({})

// get form fields
const formFields = createResource({
	url: "hrms.api.get_doctype_fields",
	params: { doctype: "Shift Request" },
	auto: true,
	transform(data) {
		if (props.id) return data
		return data.filter(
			(field) => !["employee", "employee_name", "company"].includes(field.fieldname)
		)
	},
})

// form scripts
watch(
	() => shiftRequest.value.employee,
	(employee_id) => {
		if (props.id && employee_id !== employee.data.name) {
			// if employee is not the current user, set form as read only
			setFormReadOnly()
		}
	}
)

watch(
	() => [shiftRequest.value.from_date, shiftRequest.value.to_date],
	([from_date, to_date]) => {
		validateDates(from_date, to_date)
	}
)

// helper functions
function setFormReadOnly() {
	formFields.data.map((field) => (field.read_only = true))
}

function validateDates(from_date, to_date) {
	if (!(from_date && to_date)) return

	const error_message = from_date > to_date ? __("To Date cannot be before From Date") : ""

	const from_date_field = formFields.data.find((field) => field.fieldname === "from_date")
	from_date_field.error_message = error_message
}

function validateForm() {
	shiftRequest.value.employee = employee.data.name
}
</script>
