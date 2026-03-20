# Copyright 2026 MESACHES
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CommissionSettlementLine(models.Model):
    _inherit = "commission.settlement.line"

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

    @api.depends("invoice_agent_line_id", "invoice_line_id", "settlement_id.agent_id")
    def _compute_source_invoice(self):
        for line in self:
            inv = False
            # Route 1: standard OCA field
            if line.invoice_agent_line_id and line.invoice_agent_line_id.invoice_id:
                inv = line.invoice_agent_line_id.invoice_id
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
    payment_line_ids = fields.One2many(
        comodel_name="commission.settlement.payment",
        inverse_name="settlement_id",
        string="Payment Records",
        readonly=True,
        copy=False,
    )
    payment_count = fields.Integer(
        compute="_compute_payment_amounts",
        store=True,
    )

    @api.depends("total", "payment_line_ids", "payment_line_ids.amount")
    def _compute_payment_amounts(self):
        for rec in self:
            paid = sum(rec.payment_line_ids.mapped("amount"))
            rec.amount_paid = paid
            rec.amount_residual = rec.total - paid
            rec.payment_count = len(rec.payment_line_ids)
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
            rec.payment_line_ids.unlink()
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
        return {
            "type": "ir.actions.act_window",
            "name": _("Payment Records"),
            "res_model": "commission.settlement.payment",
            "view_mode": "list,form",
            "domain": [("settlement_id", "=", self.id)],
            "context": {"create": False},
        }

    def unlink(self):
        if any(x.state == "paid" for x in self):
            raise UserError(_("You can't delete paid settlements."))
        return super().unlink()


class CommissionSettlementPayment(models.Model):
    """Payment record with full traceability to source sales invoices.

    The chain is:
      payment → settlement → settlement.line → invoice_agent_line_id
        → object_id (account.move.line) → move_id (account.move = sales invoice)
        → partner_id (customer)
    """

    _name = "commission.settlement.payment"
    _description = "Commission Settlement Payment Record"
    _order = "date desc, id desc"
    _rec_name = "display_name"
    _sql_constraints = [
        ("amount_positive", "CHECK(amount > 0)",
         "Payment amount must be positive."),
    ]

    settlement_id = fields.Many2one(
        comodel_name="commission.settlement",
        required=True,
        ondelete="cascade",
        index=True,
        string="Settlement",
    )
    agent_id = fields.Many2one(
        related="settlement_id.agent_id",
        store=True,
        index=True,
        string="Agent",
    )
    date = fields.Date(
        string="Payment Date",
        required=True,
        default=fields.Date.context_today,
    )
    amount = fields.Monetary(
        string="Amount Paid",
        currency_field="currency_id",
        required=True,
    )
    currency_id = fields.Many2one(
        related="settlement_id.currency_id",
        store=True,
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
        related="settlement_id.company_id",
        store=True,
    )

    # ── Traceability to source invoices ───────────────────────────
    # These are computed from the settlement lines to show WHERE
    # the commission comes from (which sales invoices, which customers)
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
        string="Customers",
        compute="_compute_source_invoices",
        store=True,
    )
    settlement_total = fields.Float(
        related="settlement_id.total",
        string="Settlement Total",
        store=True,
    )
    date_from = fields.Date(
        related="settlement_id.date_from",
        store=True,
        string="Period From",
    )
    date_to = fields.Date(
        related="settlement_id.date_to",
        store=True,
        string="Period To",
    )

    @api.depends("date", "agent_id.name", "amount")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _(
                "Payment %(date)s - %(agent)s (%(amount)s)",
                date=rec.date,
                agent=rec.agent_id.name or "",
                amount=f"{rec.amount:.2f}",
            )

    @api.depends(
        "settlement_id",
        "settlement_id.line_ids",
        "settlement_id.line_ids.source_invoice_id",
    )
    def _compute_source_invoices(self):
        for rec in self:
            invoices = rec.settlement_id.line_ids.mapped("source_invoice_id")
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
