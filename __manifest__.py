# Copyright 2026 MESACHES
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Commission Payment Tracking",
    "version": "18.0.1.1.0",
    "summary": "Track when agent commissions have been paid with full invoice traceability",
    "author": "MESACHES DESARROLLOS INFORMATICOS SL",
    "category": "Sales",
    "license": "AGPL-3",
    "website": "https://mesaches.com",
    "depends": [
        "account_commission_oca",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "wizards/commission_register_payment_views.xml",
        "views/res_partner_views.xml",
        "views/commission_settlement_views.xml",
        "views/commission_payment_dashboard.xml",
        "report/commission_payment_report.xml",
        "report/commission_payment_report_templates.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "post_init_hook": "post_init_hook",
}
