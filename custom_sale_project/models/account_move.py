from odoo import models, fields, api

from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move.line'

    discount_amount=fields.Float(string='Discount Amount')

class AccountMovee(models.Model):
    _inherit = 'account.move'
    picking_id = fields.Many2one(
        'stock.picking',
        string='Delivery Order',
        help="Select the related delivery order."
    )

    @api.onchange('picking_id')
    def _onchange_picking_id(self):
        """When selecting a delivery order, fill invoice lines automatically."""
        if not self.picking_id:
            return

        picking = self.picking_id
        move_lines = picking.move_ids_without_package.filtered(lambda m: m.quantity > 0)

        if not move_lines:
            raise ValidationError("The selected delivery order has no delivered products.")

        # Clear existing invoice lines
        self.invoice_line_ids = [(5, 0, 0)]

        invoice_lines = []
        for move in move_lines:
            product = move.product_id
            qty = move.quantity
            # Use the delivery price unit if filled, otherwise fallback
            price = move.delivery_price_unit  or product.lst_price

            account = (
                    product.property_account_income_id.id
                    or product.categ_id.property_account_income_categ_id.id
            )

            line_vals = {
                'product_id': product.id,
                'quantity': qty,
                'price_unit': price,
                'name': product.display_name,
                'account_id': account,
            }
            invoice_lines.append((0, 0, line_vals))

        self.invoice_line_ids = invoice_lines
