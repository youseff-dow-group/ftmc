from odoo import models, fields ,api

from odoo.exceptions import ValidationError

from jinja2.filters import do_min


class ProjectTask(models.Model):
    _inherit = 'project.task'


    product_name = fields.Char(string="Product Name")

    quantity = fields.Float(string="Quantity",default=1.00)


    sale_bom_ids = fields.One2many('sale.bom', 'task_id', string="Sale BOM")

    is_new_bom = fields.Boolean(string="Need new Bom")

    # Add margin field
    margin = fields.Float(string="Margin (%)", default=0.0)  # Margin in percentage

    # Add total_price field to store computed price with margin
    total_price = fields.Float(string="Total Price", compute="_compute_total_price", store=True)

    # Link to the created product
    product_id = fields.Many2one('product.template', string="Product", readonly=True)
    product_uom = fields.Many2one('uom.uom', string="Product Uom")
    product_purchase_uom = fields.Many2one('uom.uom', string="Purchase Uom")
    product_cat = fields.Many2one('product.category', string="Product Category")

    total_bom_cost = fields.Float(string="Total Cost", compute="_compute_total_bom_cost", store=True)

    @api.depends('sale_bom_ids.line_total')
    def _compute_total_bom_cost(self):
        for task in self:
            task.total_bom_cost = sum(line.line_total for line in task.sale_bom_ids)


    # Smart button for viewing the product
    def action_view_product(self):
        """Action to open the product form view"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Product',
            'res_model': 'product.template',
            'res_id': self.product_id.id,  # The ID of the created product
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'current',
        }

    @api.depends('sale_bom_ids.vendor_price', 'margin')
    def _compute_total_price(self):
        """Compute the total price by summing vendor prices and adding margin."""
        for task in self:
            total_vendor_price = sum(line.vendor_price for line in task.sale_bom_ids)

            task.total_price = total_vendor_price + (total_vendor_price * (task.margin / 100))

    def action_create_product_bom(self):
        """Creates a new product template and BOM when conditions are met."""
        for task in self:
            if not task.is_new_bom or not task.sale_bom_ids or task.quantity <= 0:
                raise ValidationError(
                    "Conditions not met: Ensure 'Need new BOM' is checked, Sale BOM is filled, and Quantity is positive.")

            product_template = self.env['product.template'].create({
                'name': task.product_name,
                'type': 'consu',
                'list_price': task.total_price,
                'uom_id': task.product_uom.id,
                'uom_po_id': task.product_purchase_uom.id,
                'categ_id': task.product_cat.id,

            })

            task.product_id = product_template.id

            bom = self.env['mrp.bom'].create({
                'product_tmpl_id': product_template.id,
                'product_qty': task.quantity,
                'type': 'normal',
            })

            for line in task.sale_bom_ids:
                self.env['mrp.bom.line'].create({
                    'bom_id': bom.id,
                    'product_id': line.product_id.id,
                    'product_qty': line.quantity,  # Use quantity from Sale BOM
                })

class SaleBOM(models.Model):
    _name = 'sale.bom'

    task_id = fields.Many2one('project.task', string="Task", ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Product", required=True)
    vendor_price = fields.Float(string="Cost",)
    quantity = fields.Float(string="Quantity", default=1.00)
    available_qty = fields.Float(string="Available Quantity", compute="_compute_available_qty", store=True)
    available_vendors = fields.Many2many(
        'product.supplierinfo', compute="_compute_available_vendors", store=True
    )

    vendor_partner = fields.Many2one(
        'product.supplierinfo', string="Supplier",
        domain="[('id', 'in', available_vendors)]"
    )

    discount = fields.Float(string="Discount (%)", default=0.0, help="Discount in percentage")
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id', depends=['product_id'])


    product_uom = fields.Many2one('uom.uom', string="Product Uom",domain="[('category_id', '=', product_uom_category_id)]")

    line_total = fields.Float(string="Line Total", compute="_compute_line_total", store=True)

    @api.depends('vendor_price', 'quantity')
    def _compute_line_total(self):
        for record in self:
            record.line_total = record.vendor_price * record.quantity

    @api.onchange('discount', 'vendor_price')
    def _onchange_discount(self):
        """Update the vendor price based on the discount percentage."""
        if self.vendor_price and self.discount:
            self.vendor_price = self.vendor_price * (1 - (self.discount / 100))
        elif not self.discount:
            if self.vendor_partner:
                self.vendor_price = self.vendor_partner.price
    @api.onchange('vendor_partner')
    def _onchange_vendor_partner(self):
        """Update vendor price based on selected vendor."""
        if self.vendor_partner:
            self.vendor_price = self.vendor_partner.price  # Fill vendor_price with the selected vendor's price
        else:
            self.vendor_price = 0.0  # Reset if no vendor is selected

    @api.depends('product_id')
    def _compute_available_vendors(self):
        """Compute the available suppliers for the selected product."""
        for record in self:
            if record.product_id:
                record.available_vendors = record.product_id.product_tmpl_id.seller_ids
            else:
                record.available_vendors = False  # Empty when no product is selected
    @api.depends('product_id')
    def _compute_available_qty(self):
        """Compute the available quantity across all warehouses and companies."""
        for record in self:
            record.available_qty = 0.0  # Reset before summing
            view_context = self.env.context
            allowed_companies = view_context.get('allowed_company_ids', False)

            print("Allowed Companies:", len(allowed_companies))
            print("Allowed Companies d d   d:", self.env.user.company_ids)
            print("Allowed Companies d dsdsdsd   d:", self.env.company)


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
                    print("elseee")

                    stock_quant = record.env['stock.quant'].search(
                        [('product_id', '=', record.product_id.id),('company_id', '=', self.env.company.id  )
                        ],
                    )
                    print("elseee سفخؤن",stock_quant)

                    for quant in stock_quant:
                        if quant.quantity > 0.0:
                            print("stock quanttt", quant.quantity, quant.location_id.location_id.name)
                            record.available_qty += quant.quantity if quant.quantity else 0.0
            else:
                record.available_qty = 0.0
