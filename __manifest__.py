# Copyright 2026 MESACHES
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Commission Payment Tracking",
    "version": "18.0.1.0.0",
    "summary": "Track when agent commissions have been paid with full invoice traceability",
    "author": "MESACHES, Odoo Community Association (OCA)",
    "category": "Sales",
    "license": "AGPL-3",
    "website": "https://github.com/OCA/commission",
    "depends": [
        "account_commission_oca",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizards/commission_register_payment_views.xml",
        "views/commission_settlement_views.xml",
        "views/commission_payment_dashboard.xml",
        "report/commission_payment_report.xml",
        "report/commission_payment_report_templates.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
