# Copyright 2026 MESACHES
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Migrate old settlement_id (Many2one) data to detail lines."""
    if not version:
        return

    # Check if old settlement_id column exists in payment table
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'commission_settlement_payment'
        AND column_name = 'settlement_id'
    """)
    if not cr.fetchone():
        _logger.info("No old settlement_id column found, skipping migration.")
        return

    # Count existing payment records with old-style settlement_id
    cr.execute("""
        SELECT COUNT(*) FROM commission_settlement_payment
        WHERE settlement_id IS NOT NULL
    """)
    count = cr.fetchone()[0]
    if not count:
        _logger.info("No old payment records to migrate.")
        return

    _logger.info("Migrating %d old payment records to detail lines...", count)

    # Create detail records from old payment records
    cr.execute("""
        INSERT INTO commission_settlement_payment_detail
            (payment_id, settlement_id, amount,
             create_uid, create_date, write_uid, write_date)
        SELECT
            p.id, p.settlement_id, p.amount,
            p.create_uid, p.create_date, p.write_uid, p.write_date
        FROM commission_settlement_payment p
        WHERE p.settlement_id IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM commission_settlement_payment_detail d
            WHERE d.payment_id = p.id AND d.settlement_id = p.settlement_id
        )
    """)
    migrated = cr.rowcount
    _logger.info("Created %d detail lines.", migrated)

    # Assign names to payments that don't have one
    cr.execute("""
        UPDATE commission_settlement_payment
        SET name = 'PAY/' || EXTRACT(YEAR FROM date)::text
                   || '/' || LPAD(id::text, 4, '0')
        WHERE name IS NULL OR name = '/'
    """)

    # Ensure agent_id, currency_id, company_id are set (they were related+stored)
    # The columns should already have data from the old related fields
    # Just make sure they're not null by falling back to settlement data
    cr.execute("""
        UPDATE commission_settlement_payment p
        SET agent_id = COALESCE(p.agent_id, s.agent_id),
            currency_id = COALESCE(p.currency_id, s.currency_id),
            company_id = COALESCE(p.company_id, s.company_id)
        FROM commission_settlement s
        WHERE s.id = p.settlement_id
        AND (p.agent_id IS NULL OR p.currency_id IS NULL OR p.company_id IS NULL)
    """)

    _logger.info("Migration complete.")

    # Force recomputation of stored computed fields
    env = api.Environment(cr, SUPERUSER_ID, {})
    payments = env["commission.settlement.payment"].search([])
    if payments:
        payments._compute_amount()
        payments._compute_settlement_info()
        payments._compute_source_invoices()

    settlements = env["commission.settlement"].search([
        ("state", "in", ("settled", "invoiced", "paid")),
    ])
    if settlements:
        settlements._compute_payment_amounts()
