const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const { test } = require("node:test");

function form(
  overrides = {},
  { isNew = false, workflow = true, dirty = false } = {}
) {
  let handlers;
  const buttons = new Map();
  const calls = [];
  const frappe = {
    provide() {},
    ui: { form: { on: (_doctype, value) => (handlers = value) } },
    get_list: (_doctype, filters) =>
      workflow && filters.name === "Connect Operation Plan - Payroll Entry"
        ? [{}]
        : [],
    model: { has_workflow: () => workflow },
    throw: (message) => {
      throw new Error(message);
    },
  };
  vm.runInNewContext(fs.readFileSync(`${__dirname}/payroll_entry.js`, "utf8"), {
    frappe,
    __: (value) => value,
    cint: Number,
  });
  const frm = {
    doctype: "Payroll Entry",
    doc: {
      docstatus: 0,
      workflow_state: "Plan Draft",
      employees: [{}],
      ...overrides,
    },
    is_new: () => isNew,
    is_dirty: () => dirty,
    page: {
      clear_primary_action() {},
      set_primary_action: (label, callback) => buttons.set(label, callback),
      btn_secondary: { hide() {} },
    },
    add_custom_button: (label, callback) => {
      buttons.set(label, callback);
      return { toggleClass() {} };
    },
    events: { add_context_buttons() {} },
    save: async (...args) => calls.push(["save", ...args]),
    call: async (method) => calls.push(["call", method]),
    reload_doc: async () => calls.push(["reload"]),
    refresh() {},
  };
  handlers.refresh(frm);
  return { buttons, calls };
}

test("saved draft and rejected payroll calculate through the native method without submitting", async () => {
  for (const workflow_state of ["Plan Draft", "Plan Rejected"]) {
    const { buttons, calls } = form({ workflow_state });
    assert(buttons.has("Calculate Salary Slips"));
    await buttons.get("Calculate Salary Slips")();
    assert.deepEqual(calls, [["call", "create_salary_slips"], ["reload"]]);
  }
});

test("calculation stays hidden outside editable saved payroll with employees", () => {
  for (const changes of [
    { employees: [] },
    { docstatus: 1 },
    { docstatus: 2 },
    { status: "Queued" },
    { workflow_state: "Plan Pending Approval" },
    { workflow_state: "Plan Approved" },
    { workflow_state: "Plan Cancelled" },
  ])
    assert(!form(changes).buttons.has("Calculate Salary Slips"));
  assert(!form({}, { isNew: true }).buttons.has("Calculate Salary Slips"));
  const legacy = form({}, { workflow: false });
  assert(!legacy.buttons.has("Calculate Salary Slips"));
  assert(legacy.buttons.has("Create Salary Slips"));
});

test("unsaved edits cannot calculate from a different employee roster", () => {
  const { buttons, calls } = form({}, { dirty: true });
  assert.throws(buttons.get("Calculate Salary Slips"), /Please save/);
  assert.deepEqual(calls, []);
});
