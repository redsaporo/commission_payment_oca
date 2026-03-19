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
    pay_mode = fields.Selection(
        selection=[
            ("full", "Pay full pending amount"),
            ("custom", "Custom amount per settlement"),
        ],
        string="Payment Mode",
        default="full",
        required=True,
    )
    custom_amount = fields.Float(
        string="Custom Amount",
    )
    total_pending = fields.Float(
        string="Total Pending",
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

            payment_obj.create({
                "settlement_id": settlement.id,
                "date": self.payment_date,
                "amount": amount,
                "reference": self.reference or False,
                "notes": self.notes or False,
            })

            # Recompute
            settlement._compute_payment_amounts()

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
