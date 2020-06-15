frappe.ui.form.on("Sales Invoice", {
    validate: function (frm) {
        if (frm.doc.customer && frm.doc.is_return == 0) {
            frappe.db.get_value('Customer', frm.doc.customer, ['payment_cash', 'min_cash_required_percentage_cf'])
                .then(r => {
                    if (r.message) {
                        let payment_cash = r.message.payment_cash
                        // field to be created min_cash_required_percentage_cf
                        let min_cash_required_percentage_cf = r.message.min_cash_required_percentage_cf || 100
                        let base_rounded_total = frm.doc.base_grand_total
                        let outstanding_amount = frm.doc.outstanding_amount
                        let paid_amount = flt(base_rounded_total) - flt(outstanding_amount)
                        // for SAR currency, fraction is 2. hence hard coded
                        let min_to_pay_before_save =flt( flt(base_rounded_total) * min_cash_required_percentage_cf / 100,2)
                        if (frm.doc.outstanding_amount > 0 && payment_cash == 1 && frm.doc.is_return == 0 && paid_amount < min_to_pay_before_save) {
                            frappe.validated = false;
                            frappe.msgprint(__(repl("As per the<b> PAYMENT TERMS </b>of this customer, minimum <b> SAR %(min_to_pay_before_save)s </b> must be collected to submit this invoice", {
                                'customer_name': frm.doc.customer_name,
                                'min_to_pay_before_save': min_to_pay_before_save
                            })))
                            return false;
                        }
                    }
                })
        }
    }
})
