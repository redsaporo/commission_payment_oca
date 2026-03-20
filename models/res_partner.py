# Copyright 2026 MESACHES
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    commission_payment_ids = fields.One2many(
        comodel_name="commission.settlement.payment",
        inverse_name="agent_id",
        string="Commission Payments",
    )
    commission_payment_count = fields.Integer(
        compute="_compute_commission_payment_count",
        string="Commission Payments",
    )
    commission_payment_total = fields.Float(
        compute="_compute_commission_payment_count",
        string="Total Paid",
    )

    def _compute_commission_payment_count(self):
        payment_data = self.env["commission.settlement.payment"].read_group(
            domain=[("agent_id", "in", self.ids)],
            fields=["amount:sum"],
            groupby=["agent_id"],
        )
        mapped = {
            d["agent_id"][0]: {
                "count": d["agent_id_count"],
                "total": d["amount"],
            }
            for d in payment_data
        }
        for partner in self:
            data = mapped.get(partner.id, {})
            partner.commission_payment_count = data.get("count", 0)
            partner.commission_payment_total = data.get("total", 0.0)

    def action_view_commission_payments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Commission Payments"),
            "res_model": "commission.settlement.payment",
            "view_mode": "list,form",
            "domain": [("agent_id", "=", self.id)],
            "context": {"create": False},
        }
