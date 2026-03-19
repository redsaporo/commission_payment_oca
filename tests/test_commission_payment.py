# Copyright 2026 MESACHES
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCommissionPayment(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.commission = cls.env["commission"].create({
            "name": "Test 10%", "fix_qty": 10.0,
        })
        cls.agent = cls.env["res.partner"].create({
            "name": "Agent Test",
            "agent": True,
            "agent_type": "agent",
            "commission_id": cls.commission.id,
            "settlement": "monthly",
        })
        cls.settlement = cls.env["commission.settlement"].create({
            "agent_id": cls.agent.id,
            "date_from": "2026-01-01",
            "date_to": "2026-01-31",
            "settlement_type": "manual",
        })
        cls.env["commission.settlement.line"].create({
            "settlement_id": cls.settlement.id,
            "date": "2026-01-15",
            "commission_id": cls.commission.id,
            "settled_amount": 500.0,
        })

    def test_full_payment(self):
        wiz = self.env["commission.register.payment"].with_context(
            active_ids=self.settlement.ids,
            active_model="commission.settlement",
        ).create({"payment_date": "2026-02-15", "reference": "NOM-02", "pay_mode": "full"})
        wiz.button_register()
        self.assertEqual(self.settlement.state, "paid")
        self.assertEqual(self.settlement.amount_paid, 500.0)
        self.assertEqual(self.settlement.amount_residual, 0)

    def test_partial_payment(self):
        wiz = self.env["commission.register.payment"].with_context(
            active_ids=self.settlement.ids,
            active_model="commission.settlement",
        ).create({"payment_date": "2026-02-10", "pay_mode": "custom", "custom_amount": 200.0})
        wiz.button_register()
        self.assertEqual(self.settlement.state, "settled")
        self.assertEqual(self.settlement.amount_paid, 200.0)
        self.assertEqual(self.settlement.amount_residual, 300.0)

    def test_revert(self):
        self.env["commission.settlement.payment"].create({
            "settlement_id": self.settlement.id, "date": "2026-02-15",
            "amount": 500.0, "reference": "TEST",
        })
        self.settlement.write({"state": "paid", "payment_date": "2026-02-15"})
        self.settlement.action_revert_to_settled()
        self.assertEqual(self.settlement.state, "settled")
        self.assertEqual(self.settlement.payment_count, 0)

    def test_cannot_delete_paid(self):
        self.settlement.write({"state": "paid"})
        with self.assertRaises(UserError):
            self.settlement.unlink()
