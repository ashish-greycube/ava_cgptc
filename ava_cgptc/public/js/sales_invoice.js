frappe.ui.form.on("Sales Invoice", {
    validate: function(frm) {
        if (frm.doc.customer) {
            frappe.db.get_value('Customer', frm.doc.customer,['payment_cash','min_cash_required_percentage_cf'] )
            .then(r => {
                if (r.message) {
                    let payment_cash=r.message.payment_cash
                    // field to be created min_cash_required_percentage_cf
                    let min_cash_required_percentage_cf=r.message.min_cash_required_percentage_cf || 100
                    let base_rounded_total=frm.doc.base_grand_total
                    let outstanding_amount=frm.doc.outstanding_amount
                    let paid_amount=flt(base_rounded_total)-flt(outstanding_amount)
                    let min_to_pay_before_save=Math.round(flt(base_rounded_total)*min_cash_required_percentage_cf/100)
                    if(frm.doc.outstanding_amount>0 && payment_cash==1 && frm.doc.is_return == 0 && paid_amount<min_to_pay_before_save){
						frappe.throw(__(repl("For Cash Customer : %(customer_name)s, Please receive minimum  :<b> %(min_to_pay_before_save)s </b> to proceed.", {
							'customer_name':frm.doc.customer_name,'min_to_pay_before_save':min_to_pay_before_save
						})))                        
                    }                
                }
            })             
        }
    }
})