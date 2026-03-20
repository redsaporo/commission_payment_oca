# Copyright 2026 MESACHES
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, exceptions, fields, models


class CommissionRegisterPayment(models.TransientModel):
    _name = "commission.register.payment"
    _description = "Register payment for commission settlements"

    def _default_settlement_ids(self):
        ctx = self.env.context
        if ctx.get("active_model") == "commission.settlement":
            settlements = self.env["commission.settlement"].browse(
                ctx.get("active_ids", [])
            )
            valid = settlements.filtered(
                lambda s: s.state in ("settled", "invoiced")
            )
            if not valid:
                raise exceptions.UserError(
                    _("No valid settlements to register payment.")
                )
            return valid.ids
        return []

    settlement_ids = fields.Many2many(
        comodel_name="commission.settlement",
        relation="commission_register_payment_settlement_rel",
        column1="wizard_id",
        column2="settlement_id",
        string="Settlements",
        default=lambda self: self._default_settlement_ids(),
        readonly=True,
    )
    payment_date = fields.Date(
        string="Payment Date",
        required=True,
        default=fields.Date.context_today,
    )
    reference = fields.Char(
        string="Payment Reference",
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
    pay_mode = fields.Selection(
        selection=[
            ("full", "Pay full pending amount"),
            ("custom", "Custom amount per settlement"),
        ],
        string="Payment Mode",
        default="full",
        required=True,
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        compute="_compute_summary",
    )
    custom_amount = fields.Monetary(
        string="Custom Amount",
        currency_field="currency_id",
    )
    total_pending = fields.Monetary(
        string="Total Pending",
        currency_field="currency_id",
        compute="_compute_summary",
    )
    settlement_count = fields.Integer(
        compute="_compute_summary",
    )

    @api.depends("settlement_ids")
    def _compute_summary(self):
        for wiz in self:
            wiz.total_pending = sum(
                wiz.settlement_ids.mapped("amount_residual")
            )
            wiz.settlement_count = len(wiz.settlement_ids)
            wiz.currency_id = (
                wiz.settlement_ids[:1].currency_id
                or wiz.env.company.currency_id
            )

    def button_register(self):
        self.ensure_one()
        if not self.settlement_ids:
            raise exceptions.UserError(_("No settlements selected."))

        payment_obj = self.env["commission.settlement.payment"]

        for settlement in self.settlement_ids:
            amount = (
                settlement.amount_residual
                if self.pay_mode == "full"
                else self.custom_amount
            )
            if amount <= 0:
                continue

            if self.pay_mode == "custom" and amount > settlement.amount_residual:
                raise exceptions.UserError(
                    _(
                        "Custom amount (%(amount)s) exceeds pending "
                        "(%(residual)s) for %(name)s.",
                        amount=f"{amount:.2f}",
                        residual=f"{settlement.amount_residual:.2f}",
                        name=settlement.display_name,
                    )
                )

            payment_obj.create({
                "settlement_id": settlement.id,
                "date": self.payment_date,
                "amount": amount,
                "reference": self.reference or False,
                "notes": self.notes or False,
                "payroll_ref": self.payroll_ref or False,
                "payroll_period": self.payroll_period or False,
            })

            # Flush to trigger stored computed field recomputation
            settlement.flush_recordset()

            if settlement.is_fully_paid:
                settlement.write({
                    "state": "paid",
                    "payment_date": self.payment_date,
                    "payment_ref": self.reference or False,
                    "payment_notes": self.notes or False,
                })
                settlement.message_post(
                    body=_(
                        "Commission fully paid. Date: %(date)s. "
                        "Reference: %(ref)s. Total: %(amount)s",
                        date=self.payment_date,
                        ref=self.reference or "-",
                        amount=f"{settlement.amount_paid:.2f}",
                    ),
                )
            else:
                settlement.message_post(
                    body=_(
                        "Partial payment: %(amount)s. "
                        "Date: %(date)s. Ref: %(ref)s. "
                        "Remaining: %(remaining)s",
                        amount=f"{amount:.2f}",
                        date=self.payment_date,
                        ref=self.reference or "-",
                        remaining=f"{settlement.amount_residual:.2f}",
                    ),
                )

        return {
            "type": "ir.actions.act_window",
            "name": _("Settlements"),
            "res_model": "commission.settlement",
            "view_mode": "list,form",
            "domain": [("id", "in", self.settlement_ids.ids)],
        }
