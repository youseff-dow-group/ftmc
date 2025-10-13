from odoo import models, fields, api

from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move.line'

    discount_amount=fields.Float(string='Discount Amount')
    actual_weight = fields.Float(string="Actual Weight", readonly=True)
    net_weight = fields.Float(string="Net Weight")
    gross_weight = fields.Float(string="Gross Weight")
    remarks = fields.Char(string="Remarks")
    hs_code = fields.Char(string="H.S.Code")
    country_of_origin_ids = fields.Many2many(
        'res.country',
        string="Country of Origin"
    )

class AccountMovee(models.Model):
    _inherit = 'account.move'
    picking_id = fields.Many2one(
        'stock.picking',
        string='Delivery Order',
        help="Select the related delivery order."
    )

    def _fill_invoice_lines_from_picking(self):
        """Rebuild invoice lines from the linked picking."""
        for move in self:
            if not move.picking_id:
                continue

            picking = move.picking_id
            move_lines = picking.move_ids_without_package.filtered(lambda m: m.quantity > 0)

            if not move_lines:
                raise ValidationError("The selected delivery order has no delivered products.")

            invoice_lines = []
            for line in move_lines:
                product = line.product_id
                qty = line.quantity
                price = line.delivery_price_unit or product.lst_price

                account = (
                    product.property_account_income_id.id
                    or product.categ_id.property_account_income_categ_id.id
                )

                vals = {
                    'product_id': product.id,
                    'quantity': qty,
                    'price_unit': price,
                    'name': product.display_name,
                    'account_id': account,
                    'actual_weight': line.actual_weight,
                    'net_weight': line.net_weight,
                    'gross_weight': line.gross_weight,
                    'remarks': line.remarks,
                    'country_of_origin_ids': [(6, 0, line.country_of_origin_ids.ids)],
                }
                invoice_lines.append((0, 0, vals))

            # Replace existing lines
            move.invoice_line_ids = [(5, 0, 0)] + invoice_lines

    @api.onchange('picking_id')
    def _onchange_picking_id(self):
        """Instantly refresh invoice lines when changing delivery order in the UI."""
        if self.picking_id:
            self._fill_invoice_lines_from_picking()

    @api.model
    def create(self, vals):
        record = super().create(vals)
        # Create lines only if picking_id exists and no lines are passed
        if vals.get('picking_id') and not vals.get('invoice_line_ids'):
            record._fill_invoice_lines_from_picking()
        return record

    def write(self, vals):
        res = super().write(vals)
        # Refresh lines if picking_id changes
        if 'picking_id' in vals:
            for rec in self:
                if rec.picking_id:
                    rec._fill_invoice_lines_from_picking()
        return res