
from odoo import fields, models

class MultipleProduct(models.TransientModel):
    """Create new wizard model of product list for selection"""
    _name = "multiple.product"
    _description = 'Multiple Product Selection'

    product_list_ids = fields.Many2many('product.product',
                                        string='Product List',
                                        help="Product list of all the products")

    def action_add_line(self):
        """Function for adding all the products to the order line that are
        selected from the wizard"""
        print("i am heeeeeeeeeeer ")
        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        print("active ",active_id,active_model)
        line = 'sale.bom' if active_model == 'project.task' \
            else 'sale.order.line'
        current_id = self.env['project.task'].browse(
            active_id) if active_model == 'project.task' \
            else self.env['sale.order'].browse(active_id)
        for rec in self.product_list_ids:
            print("current id ",current_id,current_id.sale_bom_ids.product_id,line,rec )
            if rec not in current_id.sale_bom_ids.product_id:
                print("i am _______________________")
                self.env[line].create({
                    'task_id': active_id,
                    'product_id': rec.id,
                })
            elif active_model == 'purchase.order':
                current_id.order_line.filtered(
                    lambda self: self.product_id == rec).product_qty += 1
            elif active_model == 'sale.order':
                current_id.order_line.filtered(
                    lambda self: self.product_id == rec).product_uom_qty += 1
