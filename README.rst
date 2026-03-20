==========================
Commission Payment Tracking
==========================

.. |badge1| image:: https://img.shields.io/badge/maturity-Beta-yellow.png
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/licence-AGPL--3-blue.png
    :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
    :alt: License: AGPL-3
.. |badge3| image:: https://img.shields.io/badge/Odoo-18.0-blueviolet.png
    :alt: Odoo 18.0
.. |badge4| image:: https://img.shields.io/badge/github-redsaporo%2Fcommission__payment__oca-lightgray.png?logo=github
    :target: https://github.com/redsaporo/commission_payment_oca
    :alt: GitHub

|badge1| |badge2| |badge3| |badge4|

This is a **community module** developed and maintained by
`MESACHES DESARROLLOS INFORMATICOS SL <https://github.com/redsaporo>`_.
It is published as open source for the benefit of the Odoo community, with no
commercial purpose.

This module is **not maintained by OCA** nor part of any OCA repository. It is a
**complementary add-on** designed to work alongside the OCA Commission module
(``account_commission_oca`` from https://github.com/OCA/commission).

It extends the OCA Commission settlement workflow to track when agent commissions
have been paid, with full traceability back to the source sales invoices.

It is designed for companies where **commission agents are employees** who are
paid through payroll, rather than suppliers paid via accounts payable. The module
provides payroll reference fields to link commission payments to specific payroll
periods or payslips.

**Table of contents**

.. contents::
   :local:

Features
--------

* **Payment state**: Adds a ``Paid`` state to the settlement workflow
  (settled / invoiced -> paid).
* **Payment records**: Each payment is recorded with date, amount, reference,
  and optional payroll reference for full audit trail.
* **Partial payments**: Support for multiple partial payments per settlement
  until fully paid.
* **Invoice traceability**: Every payment record automatically resolves the
  source sales invoices and customers that generated the commission.
* **Bulk payments**: Register payments for multiple settlements at once via the
  list view action.
* **Payment reversal**: Revert a paid settlement back to settled state, deleting
  all associated payment records.
* **Dashboard**: Pivot and graph views for payment analysis by agent and over
  time.
* **PDF report**: Commission Payment Summary report with settlement details,
  commission lines with source invoices, and payment history.
* **Payroll integration fields**: ``Payroll Reference`` and ``Payroll Period``
  fields to link payments to payroll batches (no hard dependency on ``hr``).

Dependencies
------------

* ``account_commission_oca`` (from `OCA/commission <https://github.com/OCA/commission>`_)

Configuration
-------------

No special configuration is required. The module uses the same security groups
as the base commission module:

* **Commission Manager** (``commission_oca.group_commission_manager``): Full
  access -- can register payments, revert payments, and manage payment records.
* **Commission User** (``commission_oca.group_commission_user``): Read-only
  access to payment records.

Usage
-----

#. Go to **Commissions > Settlements** and select one or more settlements in
   ``Settled`` or ``Invoiced`` state.
#. Click the **Register Payment** button (or use the bulk action from the list
   view).
#. Choose payment mode:

   * **Pay full pending amount**: Pays the entire remaining balance.
   * **Custom amount per settlement**: Enter a specific amount (must not exceed
     the pending amount).

#. Optionally fill in:

   * **Payment Reference**: e.g., bank transfer number.
   * **Payroll Reference**: e.g., ``NOM-2026-03``.
   * **Payroll Period**: e.g., ``2026-03``.

#. Click **Register Payment**. If fully paid, the settlement moves to ``Paid``
   state.
#. To print the payment summary, use **Print > Commission Payment Summary**
   from the settlement form.

Known Limitations
-----------------

* The module does not create accounting entries (journal items). It is a
  tracking/control layer only.
* There is no hard integration with ``hr_payroll``. Payroll reference fields
  are free-text. A bridge module ``commission_payment_oca_hr`` may be developed
  in the future for deeper integration.

Bug Tracker
-----------

Bugs are tracked on `GitHub Issues
<https://github.com/redsaporo/commission_payment_oca/issues>`_.
In case of trouble, please check there if your issue has already been reported.

Credits
-------

Authors
~~~~~~~

* MESACHES DESARROLLOS INFORMATICOS SL

Contributors
~~~~~~~~~~~~

* MESACHES DESARROLLOS INFORMATICOS SL

Maintainers
~~~~~~~~~~~

This module is developed and maintained by
**MESACHES DESARROLLOS INFORMATICOS SL**.

It is not part of any OCA repository. It is a free, open-source contribution
to the Odoo community, published under the AGPL-3 license with no commercial
purpose.

.. image:: https://img.shields.io/badge/maintained%20by-MESACHES-blue.png
   :alt: Maintained by MESACHES
   :target: https://github.com/redsaporo
