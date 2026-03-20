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

    def _create_wizard(self, settlement_ids=None, **kwargs):
        """Helper to create payment wizard."""
        vals = {
            "payment_date": "2026-02-15",
            "pay_mode": "full",
        }
        vals.update(kwargs)
        ids = settlement_ids or self.settlement.ids
        return self.env["commission.register.payment"].with_context(
            active_ids=ids,
            active_model="commission.settlement",
        ).create(vals)

    def _create_payment(self, settlements=None, amount=None, **kwargs):
        """Helper to create a payment record directly."""
        if settlements is None:
            settlements = self.settlement
        detail_vals = []
        for s in settlements:
            detail_vals.append((0, 0, {
                "settlement_id": s.id,
                "amount": amount or s.total,
            }))
        vals = {
            "agent_id": settlements[0].agent_id.id,
            "date": "2026-02-15",
            "currency_id": settlements[0].currency_id.id,
            "company_id": settlements[0].company_id.id,
            "detail_ids": detail_vals,
        }
        vals.update(kwargs)
        return self.env["commission.settlement.payment"].create(vals)

    # ── Core payment tests ────────────────────────────────────────

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
        payment = self._create_payment()
        self.settlement.write({"state": "paid", "payment_date": "2026-02-15"})
        self.settlement.action_revert_to_settled()
        self.assertEqual(self.settlement.state, "settled")
        self.assertEqual(self.settlement.payment_count, 0)
        # Payment should be deleted since it had no remaining details
        self.assertFalse(payment.exists())

    def test_cannot_delete_paid(self):
        self.settlement.write({"state": "paid"})
        with self.assertRaises(UserError):
            self.settlement.unlink()

    def test_overpayment_rejected(self):
        """Custom amount exceeding residual should raise UserError."""
        wiz = self._create_wizard(pay_mode="custom", custom_amount=9999.0)
        with self.assertRaises(UserError):
            wiz.button_register()

    def test_negative_amount_constraint(self):
        """Negative detail amount should be rejected by SQL constraint."""
        with self.assertRaises(Exception):
            self._create_payment(amount=-10.0)

    def test_partial_then_full(self):
        """Pay partially, then pay the rest. Settlement should become paid."""
        wiz1 = self._create_wizard(pay_mode="custom", custom_amount=200.0)
        wiz1.button_register()
        self.assertEqual(self.settlement.state, "settled")
        self.assertEqual(self.settlement.amount_residual, 300.0)
        self.assertEqual(self.settlement.payment_count, 1)

        wiz2 = self._create_wizard(pay_mode="full")
        wiz2.button_register()
        self.assertEqual(self.settlement.state, "paid")
        self.assertEqual(self.settlement.amount_residual, 0)
        self.assertEqual(self.settlement.payment_count, 2)

    def test_payroll_ref_propagation(self):
        """Payroll reference from wizard propagates to payment record."""
        wiz = self._create_wizard(
            payroll_ref="NOM-2026-01",
            payroll_period="2026-01",
        )
        wiz.button_register()
        detail = self.settlement.payment_detail_ids[0]
        payment = detail.payment_id
        self.assertEqual(payment.payroll_ref, "NOM-2026-01")
        self.assertEqual(payment.payroll_period, "2026-01")

    def test_zero_amount_skipped(self):
        """Settlement with zero residual is skipped without error."""
        wiz1 = self._create_wizard()
        wiz1.button_register()
        self.assertEqual(self.settlement.state, "paid")
        self.settlement.action_revert_to_settled()
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
        self.assertTrue(self.settlement.payment_detail_ids)

        self.settlement.action_revert_to_settled()
        self.assertEqual(self.settlement.state, "settled")
        self.assertFalse(self.settlement.payment_date)
        self.assertFalse(self.settlement.payment_ref)
        self.assertFalse(self.settlement.payment_notes)
        self.assertEqual(self.settlement.payment_count, 0)

    def test_source_invoice_computed_on_line(self):
        """source_invoice_id should be computed on settlement lines."""
        line = self.settlement.line_ids[0]
        self.assertFalse(line.source_invoice_id)
        self.assertFalse(line.source_partner_id)

    # ── Grouped payment tests ────────────────────────────────────

    def test_multi_settlement_same_agent_creates_one_payment(self):
        """Multiple settlements for the same agent = 1 payment."""
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
        wiz = self._create_wizard(
            settlement_ids=[self.settlement.id, settlement2.id],
        )
        wiz.button_register()

        self.assertEqual(self.settlement.state, "paid")
        self.assertEqual(settlement2.state, "paid")
        self.assertEqual(self.settlement.amount_paid, 500.0)
        self.assertEqual(settlement2.amount_paid, 300.0)

        # Should create exactly 1 payment record
        payments = (
            self.settlement.payment_detail_ids.mapped("payment_id")
            | settlement2.payment_detail_ids.mapped("payment_id")
        )
        self.assertEqual(len(payments), 1)
        self.assertEqual(payments.amount, 800.0)
        self.assertEqual(payments.settlement_count, 2)
        self.assertEqual(len(payments.detail_ids), 2)

    def test_multi_agent_creates_separate_payments(self):
        """Settlements for different agents = separate payments."""
        agent2 = self.env["res.partner"].create({
            "name": "Agent Two",
            "agent": True,
            "agent_type": "agent",
            "commission_id": self.commission.id,
            "settlement": "monthly",
        })
        settlement2 = self.env["commission.settlement"].create({
            "agent_id": agent2.id,
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
        wiz = self._create_wizard(
            settlement_ids=[self.settlement.id, settlement2.id],
        )
        wiz.button_register()

        self.assertEqual(self.settlement.state, "paid")
        self.assertEqual(settlement2.state, "paid")

        # 2 different payments (1 per agent)
        pay1 = self.settlement.payment_detail_ids.mapped("payment_id")
        pay2 = settlement2.payment_detail_ids.mapped("payment_id")
        self.assertEqual(len(pay1), 1)
        self.assertEqual(len(pay2), 1)
        self.assertNotEqual(pay1, pay2)
        self.assertEqual(pay1.agent_id, self.agent)
        self.assertEqual(pay2.agent_id, agent2)
        self.assertEqual(pay1.amount, 500.0)
        self.assertEqual(pay2.amount, 300.0)

    def test_payment_sequential_name(self):
        """Payment records should get sequential PAY/ names."""
        wiz = self._create_wizard()
        wiz.button_register()
        payment = self.settlement.payment_detail_ids[0].payment_id
        self.assertTrue(payment.name.startswith("PAY/"))
        self.assertNotEqual(payment.name, "/")

    def test_payment_display_name(self):
        """Payment record should have a readable display_name with name."""
        payment = self._create_payment(reference="TEST")
        self.assertIn("PAY/", payment.display_name)
        self.assertIn("Agent Test", payment.display_name)
        self.assertIn("500.00", payment.display_name)

    def test_payment_computed_fields(self):
        """Payment computed fields aggregate from all settlements."""
        settlement2 = self.env["commission.settlement"].create({
            "agent_id": self.agent.id,
            "date_from": "2026-03-01",
            "date_to": "2026-03-31",
            "settlement_type": "manual",
        })
        self.env["commission.settlement.line"].create({
            "settlement_id": settlement2.id,
            "date": "2026-03-15",
            "commission_id": self.commission.id,
            "settled_amount": 200.0,
        })
        payment = self._create_payment(
            settlements=self.settlement | settlement2,
            amount=None,
        )
        # amount is sum of detail amounts (500 + 200)
        self.assertEqual(payment.amount, 700.0)
        self.assertEqual(payment.settlement_count, 2)
        self.assertEqual(payment.settlement_total, 700.0)
        self.assertEqual(payment.date_from.isoformat(), "2026-01-01")
        self.assertEqual(payment.date_to.isoformat(), "2026-03-31")

    def test_revert_partial_keeps_payment(self):
        """Reverting one settlement from a multi-settlement payment
        keeps the payment for the remaining settlement."""
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
        # Create one payment covering both settlements
        payment = self._create_payment(
            settlements=self.settlement | settlement2,
        )
        self.settlement.write({"state": "paid", "payment_date": "2026-02-15"})
        settlement2.write({"state": "paid", "payment_date": "2026-02-15"})

        # Revert only settlement 1
        self.settlement.action_revert_to_settled()
        self.assertEqual(self.settlement.state, "settled")
        self.assertEqual(self.settlement.payment_count, 0)
        # Payment still exists for settlement2
        self.assertTrue(payment.exists())
        self.assertEqual(len(payment.detail_ids), 1)
        self.assertEqual(payment.detail_ids.settlement_id, settlement2)
        self.assertEqual(payment.amount, 300.0)

    def test_delete_payment_reverts_settlements(self):
        """Deleting a payment directly should revert settlements to settled."""
        wiz = self._create_wizard()
        wiz.button_register()
        self.assertEqual(self.settlement.state, "paid")
        payment = self.settlement.payment_detail_ids[0].payment_id
        # Delete the payment record directly
        payment.unlink()
        self.assertEqual(self.settlement.state, "settled")
        self.assertFalse(self.settlement.payment_date)
        self.assertFalse(self.settlement.payment_ref)
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
