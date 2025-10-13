
from odoo import fields, models
from odoo.exceptions import ValidationError

class MultipleProduct(models.TransientModel):
    """Create new wizard model of product list for selection"""
    _name = "multiple.product"
    _description = 'Multiple Product Selection'

    product_list_ids = fields.Many2many('product.product',
                                        string='Product List',
                                        help="Product list of all the products")

    def action_add_line(self):
        """Add selected products to the appropriate model lines."""
        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        add_type = self.env.context.get('add_type')  # used for mrp.production: 'raw' or 'finished'

        if not active_model or not active_id:
            raise ValidationError(
                "This wizard must be opened from a valid document "
                "(e.g., task, sale order, or manufacturing order)."
            )

        record = self.env[active_model].browse(active_id)

        # 🧩 Handle for project.task
        if active_model == 'project.task':
            for rec in self.product_list_ids:
                if rec not in record.sale_bom_ids.product_id:
                    self.env['sale.bom'].create({
                        'task_id': record.id,
                        'product_id': rec.id,
                        'quantity': 1.0,
                    })

        # 🧩 Handle for sale.order
        elif active_model == 'sale.order':
            for rec in self.product_list_ids:
                line = record.order_line.filtered(lambda l: l.product_id == rec)
                if line:
                    line.product_uom_qty += 1
                else:
                    self.env['sale.order.line'].create({
                        'order_id': record.id,
                        'product_id': rec.id,
                        'product_uom_qty': 1.0,
                    })

        # 🧩 Handle for mrp.production (Manufacturing Order)
        elif active_model == 'mrp.production':
            if not add_type:
                raise ValidationError("No target type specified (expected 'raw' or 'finished').")

            for rec in self.product_list_ids:
                if add_type == 'raw':
                    # Add to Raw Materials (move_raw_ids)
                    existing = record.move_raw_ids.filtered(lambda m: m.product_id == rec)
                    if existing:
                        existing.product_uom_qty += 1
                    else:
                        self.env['stock.move'].create({
                            'name': rec.display_name,
                            'product_id': rec.id,
                            'product_uom_qty': 1.0,
                            'product_uom': rec.uom_id.id,
                            'location_id': record.location_src_id.id,
                            'location_dest_id': record.location_dest_id.id,
                            'raw_material_production_id': record.id,  # link to MO
                        })

                elif add_type == 'finished':
                    # Add to Finished Products (By-Products / move_finished_ids)
                    existing = record.move_finished_ids.filtered(lambda m: m.product_id == rec)
                    if existing:
                        existing.product_uom_qty += 1
                    else:
                        self.env['stock.move'].create({
                            'name': rec.display_name,
                            'product_id': rec.id,
                            'product_uom_qty': 1.0,
                            'product_uom': rec.uom_id.id,
                            'location_id': record.location_src_id.id,
                            'location_dest_id': record.location_dest_id.id,
                            'production_id': record.id,  # link to MO finished products
                        })

        else:
            raise ValidationError(f"This wizard does not support the model '{active_model}'.")

        return {'type': 'ir.actions.act_window_close'}
