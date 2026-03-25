# Copyright 2026 MESACHES
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Recompute source_invoice fields for existing settlement lines."""
    lines = env["commission.settlement.line"].search([
        ("source_invoice_id", "=", False),
        ("settlement_id.state", "in", ("settled", "invoiced", "paid")),
    ])
    if lines:
        _logger.info(
            "Recomputing source invoice fields for %d settlement lines",
            len(lines),
        )
        lines._compute_source_invoice()
        lines._compute_commission_percent()
