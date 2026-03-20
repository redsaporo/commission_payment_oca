====================================
Control de Pago de Comisiones (Odoo)
====================================

.. |badge1| image:: https://img.shields.io/badge/estado-Beta-yellow.png
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/licencia-AGPL--3-blue.png
    :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
    :alt: Licencia: AGPL-3
.. |badge3| image:: https://img.shields.io/badge/Odoo-18.0-blueviolet.png
    :alt: Odoo 18.0
.. |badge4| image:: https://img.shields.io/badge/github-redsaporo%2Fcommission__payment__oca-lightgray.png?logo=github
    :target: https://github.com/redsaporo/commission_payment_oca
    :alt: GitHub

|badge1| |badge2| |badge3| |badge4|

Este es un **módulo comunitario** desarrollado y mantenido por
`MESACHES DESARROLLOS INFORMATICOS SL <https://github.com/redsaporo>`_.
Publicado como código abierto para beneficio de la comunidad Odoo, **sin ánimo
de lucro**.

Este módulo **no es parte de OCA** ni está mantenido por la Odoo Community
Association. Es un **complemento** diseñado para funcionar junto al módulo OCA
de comisiones (``account_commission_oca`` de https://github.com/OCA/commission).

Extiende el flujo de liquidaciones de comisiones de OCA para llevar el control
de cuándo se pagan las comisiones a los agentes, con trazabilidad completa
hasta las facturas de venta origen.

Está diseñado para empresas donde los **agentes de comisión son empleados** a
los que se les paga a través de la nómina, no como proveedores a través de
cuentas a pagar. El módulo incluye campos de referencia de nómina para vincular
los pagos de comisiones a períodos de nómina o nóminas específicas.

.. contents::
   :local:

Características
---------------

* **Estado de pago**: Añade el estado ``Pagado`` al flujo de liquidaciones
  (liquidado / facturado → pagado).
* **Registros de pago**: Cada pago queda registrado con fecha, importe,
  referencia y referencia de nómina opcional para una auditoría completa.
* **Pagos parciales**: Soporte para múltiples pagos parciales por liquidación
  hasta completar el total.
* **Trazabilidad con facturas**: Cada registro de pago resuelve automáticamente
  las facturas de venta y clientes que generaron la comisión.
* **Pagos masivos**: Registra pagos para varias liquidaciones a la vez desde la
  vista de lista.
* **Reversión de pagos**: Revierte una liquidación pagada al estado liquidado,
  eliminando todos los registros de pago asociados.
* **Panel de control**: Vistas pivot y gráficas para análisis de pagos por
  agente y evolución temporal.
* **Informe PDF**: Resumen de Pago de Comisiones con detalle de liquidación,
  líneas de comisión con facturas origen e historial de pagos.
* **Campos de nómina**: ``Referencia de Nómina`` y ``Período de Nómina`` para
  vincular pagos a lotes de nómina (sin dependencia de ``hr``).

Dependencias
------------

* ``account_commission_oca`` (de `OCA/commission <https://github.com/OCA/commission>`_)

Configuración
-------------

No requiere configuración especial. El módulo utiliza los mismos grupos de
seguridad que el módulo base de comisiones:

* **Gestor de comisiones** (``commission_oca.group_commission_manager``):
  Acceso completo — puede registrar pagos, revertir pagos y gestionar registros.
* **Usuario de comisiones** (``commission_oca.group_commission_user``):
  Acceso de solo lectura a los registros de pago.

Uso
---

#. Ir a **Comisiones > Liquidaciones** y seleccionar una o varias liquidaciones
   en estado ``Liquidado`` o ``Facturado``.
#. Pulsar el botón **Registrar Pago** (o usar la acción masiva desde la vista
   de lista).
#. Elegir el modo de pago:

   * **Pagar importe pendiente completo**: Paga todo el saldo restante.
   * **Importe personalizado por liquidación**: Introducir un importe específico
     (no puede superar el importe pendiente).

#. Opcionalmente rellenar:

   * **Referencia de pago**: p. ej., número de transferencia bancaria.
   * **Referencia de nómina**: p. ej., ``NOM-2026-03``.
   * **Período de nómina**: p. ej., ``2026-03``.

#. Pulsar **Registrar Pago**. Si queda totalmente pagado, la liquidación pasa
   a estado ``Pagado``.
#. Para imprimir el resumen, usar **Imprimir > Resumen de Pago de Comisiones**
   desde el formulario de la liquidación.

Limitaciones conocidas
----------------------

* El módulo no genera asientos contables (apuntes). Es una capa de control y
  seguimiento únicamente.
* No hay integración directa con ``hr_payroll``. Los campos de nómina son de
  texto libre. En el futuro podría desarrollarse un módulo puente
  ``commission_payment_oca_hr`` para una integración más profunda.

Seguimiento de errores
----------------------

Los errores se registran en `GitHub Issues
<https://github.com/redsaporo/commission_payment_oca/issues>`_.
Si encuentras un problema, comprueba primero si ya ha sido reportado.

Créditos
--------

Autores
~~~~~~~

* MESACHES DESARROLLOS INFORMATICOS SL

Mantenimiento
~~~~~~~~~~~~~

Este módulo es desarrollado y mantenido por
**MESACHES DESARROLLOS INFORMATICOS SL**.

No forma parte de ningún repositorio de OCA. Es una contribución libre y de
código abierto para la comunidad Odoo, publicada bajo licencia AGPL-3 sin
ánimo de lucro.

.. image:: https://img.shields.io/badge/mantenido%20por-MESACHES-blue.png
   :alt: Mantenido por MESACHES
   :target: https://github.com/redsaporo
