from odoo import models, fields ,api

from odoo.exceptions import ValidationError


class ProjectTask(models.Model):
    _inherit = 'project.task'


    product_name = fields.Char(string="Product Name")

    quantity = fields.Float(string="Quantity")


    sale_bom_ids = fields.One2many('sale.bom', 'task_id', string="Sale BOM")

    is_new_bom = fields.Boolean(string="Need new Bom")

    def action_create_product_bom(self):
        """Creates a new product template and BOM when conditions are met."""
        for task in self:
            if not task.is_new_bom or not task.sale_bom_ids or task.quantity <= 0:
                raise ValidationError(
                    "Conditions not met: Ensure 'Need new BOM' is checked, Sale BOM is filled, and Quantity is positive.")

            product_template = self.env['product.template'].create({
                'name': task.product_name,
                'type': 'consu',
                'project_template_id': False,
            })

            bom = self.env['mrp.bom'].create({
                'product_tmpl_id': product_template.id,
                'product_qty': task.quantity,
                'type': 'normal',
            })

            for line in task.sale_bom_ids:
                self.env['mrp.bom.line'].create({
                    'bom_id': bom.id,
                    'product_id': line.product_id.id,
                    'product_qty': line.quantity,
                })

class SaleBOM(models.Model):
    _name = 'sale.bom'

    task_id = fields.Many2one('project.task', string="Task", ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Product", required=True)
    product_cost = fields.Float(string="Cost", related="product_id.standard_price", store=True)
    quantity = fields.Float(string="Quantity", default=1.0)
    available_qty = fields.Float(string="Available Quantity", compute="_compute_available_qty", store=True)

    @api.depends('product_id')
    def _compute_available_qty(self):
        """Compute the available quantity across all warehouses and companies."""
        for record in self:
            record.available_qty = 0.0
            view_context = self.env.context
            allowed_companies = view_context.get('allowed_company_ids', False)

            if record.product_id:
                if len(allowed_companies) > 1:

                    for company in allowed_companies:
                        print("companyyyyy ", company)

                        stock_quant = record.env['stock.quant'].sudo().search(
                            [('product_id', '=', record.product_id.id),
                             ('company_id', '=', company)],

                        )
                        print("stooooooock ", stock_quant)
                        for quant in stock_quant:
                            if quant.quantity > 0.0:
                                print("stock quanttt", quant.quantity,quant.location_id.location_id.name)
                                record.available_qty += quant.quantity if quant.quantity else 0.0
                else:
                    stock_quant = record.env['stock.quant'].search(
                        [('product_id', '=', record.product_id.id)
                        ],
                    )
                    for quant in stock_quant:
                        if quant.quantity > 0.0:
                            record.available_qty += quant.quantity if quant.quantity else 0.0
            else:
                record.available_qty = 0.0
