frappe.ui.form.on('Payment Entry', {
	setup: function(frm) {
		frm.set_query("party_type", function() {
            var party_account_types = Object.keys(frappe.boot.party_account_types)
            const index = party_account_types.indexOf("Customer Group");
            if (index > -1) {
                party_account_types.splice(index, 1);
            }            
			return{
				"filters": {
					"name": ["in", party_account_types],
				}
			}
        });
    }
})