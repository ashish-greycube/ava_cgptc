frappe.ui.form.on("Sales Invoice", {
	customer: function(frm) {
        frappe.db.get_value('Customer', frm.doc.customer, 'payment_cash')
        .then(r => {
            if (r.message) {
                frm.set_value('payment_cash', r.message.payment_cash)
                frm.refresh_field('payment_cash')
            }
        })        
    },
    validate: function(frm) {
        if(frm.doc.outstanding_amount>0 && frm.doc.payment_cash==1){
            frappe.throw(__('For cash customer,  outstanding amount is not allowed. Please get full payment.'));
        }
    }
})