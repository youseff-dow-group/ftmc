from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import random


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_create_mo_from_unavailable_products(self):
        """Create a single MO for unavailable products, only if one does not exist yet."""
        for picking in self:
            # Check if a MO already exists for this picking
            existing_mo = self.env['mrp.production'].search([('picking_id', '=', picking.id)], limit=1)
            if existing_mo:
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Existing Manufacturing Order'),
                    'res_model': 'mrp.production',
                    'view_mode': 'form',
                    'res_id': existing_mo.id,
                    'target': 'current',
                }

            # Collect unavailable products
            unavailable_moves = []
            for move in picking.move_ids_without_package:
                product = move.product_id
                demanded_qty = move.product_uom_qty
                forecast_qty = product.qty_available - product.outgoing_qty

                if forecast_qty < demanded_qty:
                    unavailable_moves.append(move)

            if not unavailable_moves:
                raise ValidationError(_("All products are available in stock. No MO needed."))

            # Choose one main product randomly
            main_move = random.choice(unavailable_moves)
            main_product = main_move.product_id
            main_qty = main_move.product_uom_qty

            # Create the MO
            mo = self.env['mrp.production'].create({
                'product_id': main_product.id,
                'product_qty': main_qty,
                'product_uom_id': main_product.uom_id.id,
                'bom_id': False,
                'picking_id': picking.id,  # Link the MO to the picking
            })

            # Add remaining unavailable products as by-products
            byproduct_vals = []
            for move in unavailable_moves:
                if move != main_move:
                    byproduct_vals.append((0, 0, {
                        'product_id': move.product_id.id,
                        'product_uom_qty': move.product_uom_qty - move.quantity,
                        'product_uom': move.product_uom.id,
                        'name': move.product_id.display_name,
                        'location_id': mo.location_src_id.id,
                        'location_dest_id': mo.location_dest_id.id,
                        'production_id': mo.id,
                        'state': 'draft',
                    }))
            if byproduct_vals:
                mo.move_byproduct_ids = byproduct_vals

            return {
                'type': 'ir.actions.act_window',
                'name': _('Manufacturing Order'),
                'res_model': 'mrp.production',
                'view_mode': 'form',
                'res_id': mo.id,
                'target': 'current',
            }
