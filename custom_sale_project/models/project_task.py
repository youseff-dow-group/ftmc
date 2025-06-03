from odoo import models, fields, api, _

from odoo.exceptions import ValidationError, UserError

import logging

_logger = logging.getLogger(__name__)


class ProjectTask(models.Model):
    _inherit = 'project.task'

    product_name = fields.Char(string="Product Name", compute="_compute_product_name", store=True, readonly=False)

    quantity = fields.Float(string="Quantity", default=1.00)

    sale_bom_ids = fields.One2many('sale.bom', 'task_id', string="Sale BOM")

    is_new_bom = fields.Boolean(string="Need new Bom")

    # Add margin field
    margin = fields.Float(string="Margin (%)", default=0.0)  # Margin in percentage

    # Add total_price field to store computed price with margin
    total_price = fields.Float(string="Total Price", compute="_compute_total_price", store=True)

    # Link to the created product
    product_id = fields.Many2one('product.template', string="Product", readonly=True)
    # Modified product_uom to be computed from product's UOM
    product_uom = fields.Many2one(
        'uom.uom',
        string="Product Uom",
        compute="_compute_product_uoms",
        store=True,
        readonly=False,
        help="Unit of measure from the selected product"
    )

    # Modified product_purchase_uom to be computed from product's purchase UOM
    product_purchase_uom = fields.Many2one(
        'uom.uom',
        string="Purchase Uom",
        compute="_compute_product_uoms",
        store=True,
        readonly=False,
        help="Purchase unit of measure from the selected product"
    )
    product_cat = fields.Many2one('product.category', compute="_compute_product_uoms",
        store=True,
        readonly=False, string="Product Category")

    total_bom_cost = fields.Float(string="Total Cost", compute="_compute_total_bom_cost", store=True)

    # Add reference to sale order
    sale_order_id = fields.Many2one('sale.order', string="Sale Order Line", readonly=True)

    @api.depends('product_id')
    def _compute_product_uoms(self):
        """Compute product UOMs from the selected product's UOMs"""
        for task in self:
            if task.product_id:
                # Set product UOM from product's uom_id
                task.product_uom = task.product_id.uom_id.id if task.product_id.uom_id else False
                # Set purchase UOM from product's uom_po_id
                task.product_purchase_uom = task.product_id.uom_po_id.id if task.product_id.uom_po_id else False

                task.product_cat = task.product_id.categ_id.id if task.product_id.categ_id else False
            else:
                task.product_uom = False
                task.product_purchase_uom = False
                task.product_cat = False

    @api.depends('name')
    def _compute_product_name(self):
        """Compute product name based on project name"""
        for task in self:
            if task.name:
                task.product_name = task.name
            else:
                task.product_name = ''

    @api.depends('sale_bom_ids.line_total','sale_bom_ids.vendor_price','margin')
    def _compute_total_bom_cost(self):
        for task in self:
            total_bom_cost = sum(line.line_total for line in task.sale_bom_ids)
            task.total_bom_cost = total_bom_cost + (total_bom_cost * (task.margin / 100))


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



            # Create product template
            product_template = self.env['product.template'].sudo().create({
                'name': task.product_name,
                'type': 'consu',
                'list_price': task.total_bom_cost,
                'uom_id': task.product_uom.id,
                'uom_po_id': task.product_purchase_uom.id,
                'categ_id': task.product_cat.id,
                'description_sale': task.product_name,
            })

            task.product_id = product_template.id

            # Create BOM
            bom = self.env['mrp.bom'].sudo().create({
                'product_tmpl_id': product_template.id,
                'product_qty': task.quantity,
                'type': 'normal',
            })

            # Create BOM lines
            for line in task.sale_bom_ids:
                self.env['mrp.bom.line'].sudo().create({
                    'bom_id': bom.id,
                    'product_id': line.product_id.id,
                    'product_qty': line.quantity,  # Use quantity from Sale BOM
                    'display_type': line.display_type,
                    'name': line.name,
                    'sequence': line.sequence,
                })

            # Update the product in the sale order line
            self._update_sale_order_line_product(product_template)

            # Return success notification
            return {
                'type': 'ir.actions.act_window',
                'name': _('Sale Order'),
                'res_model': 'sale.order',
                'res_id': task.sale_order_id.id,
                'view_mode': 'form',
                'view_type': 'form',
                'target': 'current',
            }

    def _update_sale_order_line_product(self, product_template):
        """Update the product in the related sale order line."""
        self.ensure_one()

        # Check if we have a sale order
        if not self.sale_order_id:
            _logger.warning(f"No sale order found for task {self.name} (ID: {self.id})")
            return False

        # Find the sale order line that references this task
        sale_line = self.env['sale.order.line'].search([
            ('order_id', '=', self.sale_order_id.id),
            ('task_id', '=', self.id)
        ], limit=1)

        if sale_line:
            self._update_sale_line_with_new_product(sale_line, product_template)
            return True

        # Fallback: try to find by matching name
        sale_line = self.env['sale.order.line'].search([
            ('order_id', '=', self.sale_order_id.id),
            ('name', 'ilike', self.name)
        ], limit=1)

        if sale_line:
            self._update_sale_line_with_new_product(sale_line, product_template)
            return True

        # If still not found, try to find by product name
        if self.name:
            sale_line = self.env['sale.order.line'].search([
                ('order_id', '=', self.sale_order_id.id),
                ('product_id.name', 'ilike', self.name)
            ], limit=1)

            if sale_line:
                self._update_sale_line_with_new_product(sale_line, product_template)
                return True

        # If no matching line found, log a warning
        _logger.warning(
            f"No matching sale order line found for task {self.name} (ID: {self.id}) in sale order {self.sale_order_id.name}")
        return False

    def _update_sale_line_with_new_product(self, sale_line, product_template):
        """Update a specific sale order line with the new product."""
        if not sale_line:
            return False

        # Get the product.product variant from the template
        product_variant = self.env['product.product'].search(
            [('product_tmpl_id', '=', product_template.id)], limit=1)

        if product_variant:
            # Update the sale order line with the new product
            sale_line.write({
                'product_id': product_variant.id,
                'name': product_template.name,
                'price_unit': product_template.list_price,
            })
            # Log the successful update
            _logger.info(f"Updated sale order line {sale_line.id} with new product {product_template.name}")
            return True

        return False


class SaleBOM(models.Model):
    _name = 'sale.bom'

    task_id = fields.Many2one('project.task', string="Task", ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=False)
    vendor_price = fields.Float(string="Supplier Cost")
    cost = fields.Float(
        string="Cost",
        related='product_id.standard_price',
        readonly=True,
        groups="custom_sale_project.group_see_bom_cost",  # Replace 'your_module_name' with your actual module name
        help="Product standard cost from product profile"
    )
    quantity = fields.Float(string="Quantity", default=1.00)
    available_qty = fields.Float(string="Available Quantity", compute="_compute_available_qty", store=True)
    available_vendors = fields.Many2many(
        'product.supplierinfo', compute="_compute_product_related_data", store=True
    )

    vendor_partner = fields.Many2one(
        'product.supplierinfo', string="Supplier",
        domain="[('id', 'in', available_vendors)]"
    )

    discount = fields.Float(string="Discount (%)", default=0.0, help="Discount in percentage")
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id', depends=['product_id'])

    product_uom = fields.Many2one(
        'uom.uom',
        string="Product Uom",
        compute="_compute_product_uom",
        store=True,
        readonly=[False],
        domain="[('category_id', '=', product_uom_category_id)]",
        help="Unit of measure from the selected product"
    )

    line_total = fields.Float(string="Line Total", compute="_compute_line_total", store=True)



    # Fields specifying custom line logic
    display_type = fields.Selection(
        selection=[
            ('line_section', "Section"),
            ('line_note', "Note"),
        ],
        default=False)

    sequence = fields.Integer(string="Sequence", default=10)

    name = fields.Text(
        string="Description",
        readonly=False)

    @api.depends('product_id')
    def _compute_product_uom(self):
        """Compute product UOM from the selected product's UOM"""
        for record in self:
            if record.product_id and record.product_id.uom_id:
                record.product_uom = record.product_id.uom_id.id
            else:
                record.product_uom = False

    @api.constrains('display_type', 'product_id')
    def _check_product_id_required(self):
        for record in self:
            if not record.display_type and not record.product_id:
                raise ValidationError("You must set a Product for regular lines.")

    @api.model
    def create(self, vals_list):
        if vals_list.get('display_type'):
            vals_list.update(product_id=False, quantity=0)
        return super().create(vals_list)

    def write(self, values):

        if 'display_type' in values and self.filtered(lambda line: line.display_type != values.get('display_type')):
            raise UserError(
                _("You cannot change the type of a warranty order line. Instead you should delete the current line and create a new line of the proper type."))
        return super().write(values)

    @api.depends('vendor_price', 'quantity')
    def _compute_line_total(self):
        for record in self:
            record.line_total = record.vendor_price * record.quantity


    @api.onchange('product_id','task_id')
    def _onchange_product_id(self):
        """Set the first available vendor when a product is selected."""
        for record in self:
            # Reset vendor and price if no product is selected
            if not record.product_id:
                record.vendor_partner = False
                record.vendor_price = 0.0
                return

            # Compute available vendors
            sellers = record.product_id.product_tmpl_id.seller_ids
            record.available_vendors = sellers

            # Set the first vendor if available
            if sellers:
                record.vendor_partner = sellers[0].id
                record.vendor_price = sellers[0].price

                # Set the name from the product if it's empty
                if not record.name:
                    record.name = record.product_id.description_sale
            else:
                # If no vendors, set price from product standard price
                record.vendor_price = record.product_id.standard_price
                record.name = record.product_id.description_sale

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

    @api.depends('product_id', 'task_id')
    def _compute_product_related_data(self):
        for record in self:
            if not record.product_id:
                record.vendor_partner = False
                record.vendor_price = 0.0
                continue

            # Available vendors
            sellers = record.product_id.product_tmpl_id.seller_ids
            record.available_vendors = sellers

            # Default to first seller
            if sellers:
                record.vendor_partner = sellers[0].id
                record.vendor_price = sellers[0].price
            else:
                record.vendor_price = record.product_id.standard_price

            if not record.name:
                record.name = record.product_id.description_sale

    @api.depends('vendor_price', 'discount')
    def _compute_discounted_price(self):
        for record in self:
            if record.discount:
                record.discounted_price = record.vendor_price * (1 - (record.discount / 100))
            else:
                record.discounted_price = record.vendor_price

    @api.depends('vendor_partner')
    def _compute_vendor_price(self):
        for record in self:
            record.vendor_price = record.vendor_partner.price if record.vendor_partner else 0.0

    @api.depends('product_id')
    def _compute_available_vendors(self):
        """Compute the available suppliers for the selected product."""
        for record in self:
            print("hellllllllllllllllllllllllll")
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

            print("Allowed Companies:", (allowed_companies))
            print("Allowed Companies d d   d:", self.env.user.company_ids)
            print("Allowed Companies d dsdsdsd   d:", self.env.company)

            if record.product_id:
                if allowed_companies and len(allowed_companies) > 1:

                    for company in allowed_companies:
                        print("companyyyyy ", company)

                        stock_quant = record.env['stock.quant'].sudo().search(
                            [('product_id', '=', record.product_id.id),
                             ('company_id', '=', company)],

                        )
                        print("stooooooock ", stock_quant)
                        for quant in stock_quant:
                            if quant.quantity > 0.0:
                                print("stock quanttt", quant.quantity, quant.location_id.location_id.name)
                                record.available_qty += quant.quantity if quant.quantity else 0.0
                else:
                    print("elseee")

                    stock_quant = record.env['stock.quant'].search(
                        [('product_id', '=', record.product_id.id), ('company_id', '=', self.env.company.id)
                         ],
                    )
                    print("elseee سفخؤن", stock_quant)

                    for quant in stock_quant:
                        if quant.quantity > 0.0:
                            print("stock quanttt", quant.quantity, quant.location_id.location_id.name)
                            record.available_qty += quant.quantity if quant.quantity else 0.0
            else:
                record.available_qty = 0.0
