# Copyright 2026 MESACHES
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CommissionSettlementLine(models.Model):
    _inherit = "commission.settlement.line"

    # ── Source invoice traceability ───────────────────────────────
    source_invoice_id = fields.Many2one(
        comodel_name="account.move",
        string="Source Invoice",
        compute="_compute_source_invoice",
        store=True,
    )
    source_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Source Customer",
        compute="_compute_source_invoice",
        store=True,
    )
    source_invoice_date = fields.Date(
        string="Invoice Date",
        compute="_compute_source_invoice",
        store=True,
    )
    source_invoice_amount = fields.Monetary(
        string="Invoice Total",
        currency_field="currency_id",
        compute="_compute_source_invoice",
        store=True,
    )
    source_invoice_payment_state = fields.Selection(
        string="Invoice Payment",
        selection=[
            ("not_paid", "Not Paid"),
            ("in_payment", "In Payment"),
            ("paid", "Paid"),
            ("partial", "Partial"),
            ("reversed", "Reversed"),
        ],
        compute="_compute_source_invoice",
        store=True,
    )
    source_invoice_ref = fields.Char(
        string="Customer Ref",
        compute="_compute_source_invoice",
        store=True,
    )
    source_product_name = fields.Char(
        string="Product/Service",
        compute="_compute_source_invoice",
        store=True,
    )
    source_invoice_line_amount = fields.Monetary(
        string="Commission Base",
        currency_field="currency_id",
        compute="_compute_source_invoice",
        store=True,
    )

    # ── Commission details ────────────────────────────────────────
    commission_type = fields.Selection(
        related="commission_id.commission_type",
        string="Commission Type",
        store=True,
    )
    commission_percent = fields.Float(
        string="Commission %",
        compute="_compute_commission_percent",
        store=True,
    )

    @api.depends("invoice_agent_line_id", "invoice_line_id", "settlement_id.agent_id")
    def _compute_source_invoice(self):
        for line in self:
            inv = False
            agent_line = False
            # Route 1: standard OCA field
            if line.invoice_agent_line_id:
                agent_line = line.invoice_agent_line_id
                if agent_line.invoice_id:
                    inv = agent_line.invoice_id
            # Route 2: related field
            elif line.invoice_line_id and line.invoice_line_id.move_id:
                inv = line.invoice_line_id.move_id
            # Route 3: reverse search by match
            else:
                agent_line = self.env["account.invoice.line.agent"].search([
                    ("agent_id", "=", line.settlement_id.agent_id.id),
                    ("commission_id", "=", line.commission_id.id),
                    ("amount", "=", line.settled_amount),
                    ("settled", "=", True),
                    ("invoice_date", ">=", line.settlement_id.date_from),
                    ("invoice_date", "<=", line.settlement_id.date_to),
                ], limit=1)
                if agent_line and agent_line.invoice_id:
                    inv = agent_line.invoice_id

            line.source_invoice_id = inv
            line.source_partner_id = inv.partner_id if inv else False
            line.source_invoice_date = inv.invoice_date if inv else False
            line.source_invoice_amount = inv.amount_total if inv else 0.0
            line.source_invoice_payment_state = (
                inv.payment_state if inv else False
            )
            line.source_invoice_ref = inv.ref if inv else False

            # Product name and line amount from the invoice line
            move_line = (
                agent_line.object_id
                if agent_line and hasattr(agent_line, "object_id")
                else line.invoice_line_id
            )
            if move_line:
                line.source_product_name = (
                    move_line.product_id.display_name
                    if move_line.product_id
                    else move_line.name or ""
                )
                line.source_invoice_line_amount = abs(move_line.price_subtotal)
            else:
                line.source_product_name = False
                line.source_invoice_line_amount = 0.0

    @api.depends("settled_amount", "source_invoice_line_amount", "commission_id")
    def _compute_commission_percent(self):
        for line in self:
            pct = 0.0
            if line.commission_id:
                if line.commission_id.commission_type == "fixed":
                    pct = line.commission_id.fix_qty
                elif line.source_invoice_line_amount:
                    # Derive percentage from amounts
                    pct = (
                        line.settled_amount
                        / line.source_invoice_line_amount
                        * 100
                    )
            line.commission_percent = pct


class CommissionSettlement(models.Model):
    _inherit = "commission.settlement"

    # ── New state ──────────────────────────────────────────────────
    state = fields.Selection(
        selection_add=[("paid", "Paid")],
        ondelete={"paid": "set default"},
    )

    # ── Payment tracking fields ───────────────────────────────────
    payment_date = fields.Date(
        string="Payment Date",
        readonly=True,
        tracking=True,
        copy=False,
    )
    payment_ref = fields.Char(
        string="Payment Reference",
        readonly=True,
        tracking=True,
        copy=False,
    )
    payment_notes = fields.Text(
        string="Payment Notes",
        readonly=True,
        copy=False,
    )

    # ── Computed amounts ──────────────────────────────────────────
    amount_paid = fields.Monetary(
        string="Amount Paid",
        currency_field="currency_id",
        compute="_compute_payment_amounts",
        store=True,
    )
    amount_residual = fields.Monetary(
        string="Amount Pending",
        currency_field="currency_id",
        compute="_compute_payment_amounts",
        store=True,
    )
    is_fully_paid = fields.Boolean(
        compute="_compute_payment_amounts",
        store=True,
    )

    # ── Payment records ───────────────────────────────────────────
    payment_detail_ids = fields.One2many(
        comodel_name="commission.settlement.payment.detail",
        inverse_name="settlement_id",
        string="Payment Details",
        readonly=True,
        copy=False,
    )
    payment_count = fields.Integer(
        compute="_compute_payment_amounts",
        store=True,
    )

    @api.depends("total", "payment_detail_ids", "payment_detail_ids.amount")
    def _compute_payment_amounts(self):
        for rec in self:
            paid = sum(rec.payment_detail_ids.mapped("amount"))
            rec.amount_paid = paid
            rec.amount_residual = rec.total - paid
            rec.payment_count = len(rec.payment_detail_ids.mapped("payment_id"))
            rec.is_fully_paid = paid >= rec.total and rec.total > 0

    # ── Actions ───────────────────────────────────────────────────
    def action_register_payment(self):
        valid = self.filtered(lambda s: s.state in ("settled", "invoiced"))
        if not valid:
            raise UserError(
                _("Only settlements in 'Settled' or 'Invoiced' state "
                  "can receive a payment registration.")
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Register Commission Payment"),
            "res_model": "commission.register.payment",
            "target": "new",
            "view_mode": "form",
            "context": {
                "active_ids": valid.ids,
                "active_model": "commission.settlement",
            },
        }

    def action_revert_to_settled(self):
        for rec in self:
            if rec.state != "paid":
                raise UserError(_("Only paid settlements can be reverted."))
            details = rec.payment_detail_ids
            payments = details.mapped("payment_id")
            details.unlink()
            # Delete payments that have no more detail lines
            for payment in payments:
                if not payment.detail_ids:
                    payment.unlink()
            rec.write({
                "state": "settled",
                "payment_date": False,
                "payment_ref": False,
                "payment_notes": False,
            })
            rec.message_post(
                body=_("Payment reverted. Settlement returned to settled."),
            )

    def action_view_payment_lines(self):
        self.ensure_one()
        payment_ids = self.payment_detail_ids.mapped("payment_id").ids
        return {
            "type": "ir.actions.act_window",
            "name": _("Payment Records"),
            "res_model": "commission.settlement.payment",
            "view_mode": "list,form",
            "domain": [("id", "in", payment_ids)],
            "context": {"create": False},
        }

    def unlink(self):
        if any(x.state == "paid" for x in self):
            raise UserError(_("You can't delete paid settlements."))
        return super().unlink()


# ═══════════════════════════════════════════════════════════════════
# Payment detail: links one payment to one settlement with an amount
# ═══════════════════════════════════════════════════════════════════
class CommissionSettlementPaymentDetail(models.Model):
    _name = "commission.settlement.payment.detail"
    _description = "Commission Payment Detail Line"
    _sql_constraints = [
        ("amount_positive", "CHECK(amount > 0)",
         "Detail amount must be positive."),
    ]

    payment_id = fields.Many2one(
        comodel_name="commission.settlement.payment",
        required=True,
        ondelete="cascade",
        index=True,
        string="Payment",
    )
    settlement_id = fields.Many2one(
        comodel_name="commission.settlement",
        required=True,
        ondelete="restrict",
        index=True,
        string="Settlement",
    )
    amount = fields.Monetary(
        string="Amount Paid",
        currency_field="currency_id",
        required=True,
    )
    currency_id = fields.Many2one(
        related="payment_id.currency_id",
    )

    # Related fields for convenience in views
    settlement_date_from = fields.Date(
        related="settlement_id.date_from",
        string="Period From",
    )
    settlement_date_to = fields.Date(
        related="settlement_id.date_to",
        string="Period To",
    )
    settlement_total = fields.Float(
        related="settlement_id.total",
        string="Settlement Total",
    )
    payment_date = fields.Date(
        related="payment_id.date",
        string="Date",
    )
    payment_reference = fields.Char(
        related="payment_id.reference",
        string="Reference",
    )
    payment_name = fields.Char(
        related="payment_id.name",
        string="Payment Number",
    )


# ═══════════════════════════════════════════════════════════════════
# Payment record: one per agent, covers multiple settlements
# ═══════════════════════════════════════════════════════════════════
class CommissionSettlementPayment(models.Model):
    """Payment record grouped by agent with full traceability.

    One payment can cover multiple settlements for the same agent.
    The detail lines track the per-settlement amount breakdown.
    """

    _name = "commission.settlement.payment"
    _description = "Commission Settlement Payment Record"
    _order = "name desc, date desc, id desc"
    _rec_name = "name"

    name = fields.Char(
        string="Number",
        readonly=True,
        default="/",
        copy=False,
        index=True,
    )
    agent_id = fields.Many2one(
        comodel_name="res.partner",
        string="Agent",
        required=True,
        index=True,
    )
    date = fields.Date(
        string="Payment Date",
        required=True,
        default=fields.Date.context_today,
    )
    amount = fields.Monetary(
        string="Amount Paid",
        currency_field="currency_id",
        compute="_compute_amount",
        store=True,
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    reference = fields.Char(
        string="Reference",
    )
    notes = fields.Text(
        string="Notes",
    )
    payroll_ref = fields.Char(
        string="Payroll Reference",
        help="Reference to the payslip or payroll batch",
    )
    payroll_period = fields.Char(
        string="Payroll Period",
        help="e.g., 2026-03, NOM-2026-Q1",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    # ── Detail lines (one per settlement) ─────────────────────────
    detail_ids = fields.One2many(
        comodel_name="commission.settlement.payment.detail",
        inverse_name="payment_id",
        string="Settlement Details",
    )

    # ── Computed from details ─────────────────────────────────────
    settlement_count = fields.Integer(
        compute="_compute_settlement_info",
        store=True,
        string="Settlements",
    )
    settlement_total = fields.Float(
        compute="_compute_settlement_info",
        store=True,
        string="Commission Total",
    )
    date_from = fields.Date(
        compute="_compute_settlement_info",
        store=True,
        string="Period From",
    )
    date_to = fields.Date(
        compute="_compute_settlement_info",
        store=True,
        string="Period To",
    )

    # ── Traceability to source invoices ───────────────────────────
    source_invoice_ids = fields.Many2many(
        comodel_name="account.move",
        string="Source Sales Invoices",
        compute="_compute_source_invoices",
        store=True,
    )
    source_invoice_count = fields.Integer(
        compute="_compute_source_invoices",
        store=True,
    )
    source_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        string="Customers",
        compute="_compute_source_invoices",
        store=True,
    )
    source_invoice_names = fields.Char(
        string="Invoices",
        compute="_compute_source_invoices",
        store=True,
    )
    source_partner_names = fields.Char(
        string="Customer Names",
        compute="_compute_source_invoices",
        store=True,
    )

    # ── All commission lines (from all linked settlements) ────────
    commission_line_ids = fields.Many2many(
        comodel_name="commission.settlement.line",
        compute="_compute_commission_lines",
        string="Commission Lines",
    )

    # ── Computes ──────────────────────────────────────────────────

    @api.depends("detail_ids.settlement_id")
    def _compute_commission_lines(self):
        for rec in self:
            settlements = rec.detail_ids.mapped("settlement_id")
            rec.commission_line_ids = settlements.mapped("line_ids")

    @api.depends("detail_ids.amount")
    def _compute_amount(self):
        for rec in self:
            rec.amount = sum(rec.detail_ids.mapped("amount"))

    @api.depends("detail_ids.settlement_id")
    def _compute_settlement_info(self):
        for rec in self:
            settlements = rec.detail_ids.mapped("settlement_id")
            rec.settlement_count = len(settlements)
            rec.settlement_total = sum(settlements.mapped("total"))
            if settlements:
                rec.date_from = min(settlements.mapped("date_from"))
                rec.date_to = max(settlements.mapped("date_to"))
            else:
                rec.date_from = False
                rec.date_to = False

    @api.depends(
        "detail_ids.settlement_id.line_ids.source_invoice_id",
    )
    def _compute_source_invoices(self):
        for rec in self:
            settlements = rec.detail_ids.mapped("settlement_id")
            invoices = settlements.mapped("line_ids.source_invoice_id")
            partners = invoices.mapped("partner_id")
            rec.source_invoice_ids = invoices
            rec.source_invoice_count = len(invoices)
            rec.source_partner_ids = partners
            rec.source_invoice_names = (
                ", ".join(invoices.mapped("name")) if invoices else False
            )
            rec.source_partner_names = (
                ", ".join(partners.mapped("name")) if partners else False
            )

    @api.depends("name", "agent_id.name", "amount")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (
                f"{rec.name} - {rec.agent_id.name or ''} ({rec.amount:.2f})"
            )

    # ── CRUD ──────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code(
                        "commission.settlement.payment"
                    ) or "/"
                )
        return super().create(vals_list)

    def unlink(self):
        """Revert linked settlements back to settled when payment is deleted."""
        settlements = self.mapped("detail_ids.settlement_id").filtered(
            lambda s: s.state == "paid"
        )
        res = super().unlink()
        # After deleting the payment (and cascade-deleted details),
        # revert settlements that are no longer fully paid
        for settlement in settlements:
            settlement.flush_recordset()
            if not settlement.is_fully_paid:
                settlement.write({
                    "state": "settled",
                    "payment_date": False,
                    "payment_ref": False,
                    "payment_notes": False,
                })
                settlement.message_post(
                    body=_("Payment deleted. Settlement returned to settled."),
                )
        return res

    # ── Actions ───────────────────────────────────────────────────

    def action_view_source_invoices(self):
        self.ensure_one()
        if not self.source_invoice_ids:
            raise UserError(_("No source invoices found."))
        action = {
            "type": "ir.actions.act_window",
            "name": _("Source Invoices"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", self.source_invoice_ids.ids)],
            "context": {"create": False},
        }
        if len(self.source_invoice_ids) == 1:
            action["view_mode"] = "form"
            action["res_id"] = self.source_invoice_ids.id
        return action
