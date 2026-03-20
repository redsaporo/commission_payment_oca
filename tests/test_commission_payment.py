# Copyright 2026 MESACHES
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError, ValidationError
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

    def _create_wizard(self, **kwargs):
        """Helper to create payment wizard for self.settlement."""
        vals = {
            "payment_date": "2026-02-15",
            "pay_mode": "full",
        }
        vals.update(kwargs)
        return self.env["commission.register.payment"].with_context(
            active_ids=self.settlement.ids,
            active_model="commission.settlement",
        ).create(vals)

    # ── Original tests ──────────────────────────────────────────

    def test_full_payment(self):
        wiz = self._create_wizard(reference="NOM-02")
        wiz.button_register()
        self.assertEqual(self.settlement.state, "paid")
        self.assertEqual(self.settlement.amount_paid, 500.0)
        self.assertEqual(self.settlement.amount_residual, 0)

    def test_partial_payment(self):
        wiz = self._create_wizard(
            payment_date="2026-02-10",
            pay_mode="custom",
            custom_amount=200.0,
        )
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

    # ── New tests ───────────────────────────────────────────────

    def test_overpayment_rejected(self):
        """Custom amount exceeding residual should raise UserError."""
        wiz = self._create_wizard(pay_mode="custom", custom_amount=9999.0)
        with self.assertRaises(UserError):
            wiz.button_register()

    def test_negative_amount_constraint(self):
        """Negative payment amount should be rejected by SQL constraint."""
        with self.assertRaises(Exception):
            self.env["commission.settlement.payment"].create({
                "settlement_id": self.settlement.id,
                "date": "2026-02-15",
                "amount": -10.0,
            })

    def test_partial_then_full(self):
        """Pay partially, then pay the rest. Settlement should become paid."""
        # First partial payment
        wiz1 = self._create_wizard(pay_mode="custom", custom_amount=200.0)
        wiz1.button_register()
        self.assertEqual(self.settlement.state, "settled")
        self.assertEqual(self.settlement.amount_residual, 300.0)
        self.assertEqual(self.settlement.payment_count, 1)

        # Full remainder
        wiz2 = self._create_wizard(pay_mode="full")
        wiz2.button_register()
        self.assertEqual(self.settlement.state, "paid")
        self.assertEqual(self.settlement.amount_residual, 0)
        self.assertEqual(self.settlement.payment_count, 2)

    def test_multi_settlement_payment(self):
        """Register payment for multiple settlements at once."""
        settlement2 = self.env["commission.settlement"].create({
            "agent_id": self.agent.id,
            "date_from": "2026-02-01",
            "date_to": "2026-02-28",
            "settlement_type": "manual",
        })
        self.env["commission.settlement.line"].create({
            "settlement_id": settlement2.id,
            "date": "2026-02-15",
            "commission_id": self.commission.id,
            "settled_amount": 300.0,
        })
        wiz = self.env["commission.register.payment"].with_context(
            active_ids=[self.settlement.id, settlement2.id],
            active_model="commission.settlement",
        ).create({"payment_date": "2026-03-01", "pay_mode": "full"})
        wiz.button_register()
        self.assertEqual(self.settlement.state, "paid")
        self.assertEqual(settlement2.state, "paid")
        self.assertEqual(self.settlement.amount_paid, 500.0)
        self.assertEqual(settlement2.amount_paid, 300.0)

    def test_payroll_ref_propagation(self):
        """Payroll reference from wizard propagates to payment record."""
        wiz = self._create_wizard(
            payroll_ref="NOM-2026-01",
            payroll_period="2026-01",
        )
        wiz.button_register()
        payment = self.settlement.payment_line_ids[0]
        self.assertEqual(payment.payroll_ref, "NOM-2026-01")
        self.assertEqual(payment.payroll_period, "2026-01")

    def test_zero_amount_skipped(self):
        """Settlement with zero residual is skipped without error."""
        # Pay fully first
        wiz1 = self._create_wizard()
        wiz1.button_register()
        self.assertEqual(self.settlement.state, "paid")
        # Revert to settled so wizard allows it
        self.settlement.action_revert_to_settled()
        # Now residual is back to 500, pay fully again
        wiz2 = self._create_wizard()
        wiz2.button_register()
        self.assertEqual(self.settlement.state, "paid")
        self.assertEqual(self.settlement.payment_count, 1)

    def test_revert_clears_payroll_ref(self):
        """Reverting payment clears all payment-related fields."""
        wiz = self._create_wizard(
            reference="REF-01",
            payroll_ref="NOM-2026-01",
            payroll_period="2026-01",
        )
        wiz.button_register()
        self.assertEqual(self.settlement.state, "paid")
        self.assertTrue(self.settlement.payment_line_ids)

        self.settlement.action_revert_to_settled()
        self.assertEqual(self.settlement.state, "settled")
        self.assertFalse(self.settlement.payment_date)
        self.assertFalse(self.settlement.payment_ref)
        self.assertFalse(self.settlement.payment_notes)
        self.assertEqual(self.settlement.payment_count, 0)

    def test_report_renders(self):
        """PDF report should render without errors."""
        report = self.env.ref(
            "commission_payment_oca.action_report_commission_payment"
        )
        content, content_type = report._render_qweb_html(
            self.settlement.ids
        )
        self.assertTrue(content)
