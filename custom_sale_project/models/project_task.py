from odoo import models, fields, api, _

from odoo.exceptions import ValidationError, UserError

import logging
from server.odoo.tools.populate import compute

_logger = logging.getLogger(__name__)


class ProjectTask(models.Model):
    _inherit = 'project.task'
    _rec_name = 'display_name'

    product_name = fields.Char(string="Product Name", compute="_compute_product_name", store=True, readonly=False)

    description_name = fields.Text(string="Description Name", help="Description to be used when creating the product")

    quantity = fields.Float(string="Quantity", default=1.00)

    sale_bom_ids = fields.One2many('sale.bom', 'task_id', string="Sale BOM")

    is_new_bom = fields.Boolean(string="Need new Bom")

    # Add margin field
    margin = fields.Float(string="Margin (%)", default=0.0)  # Margin in percentage

    discount = fields.Float(string="Discount (%)", default=0.0, help="Discount percentage applied to the total")

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

    # Sale order references
    sale_order_id = fields.Many2one('sale.order', string="Sale Order")
    sale_order_line_id = fields.Many2one('sale.order.line', string="Sale Order Line")

    # New field: Reference Sales Order (readonly char field)
    reference_sales_order = fields.Char(
        string="Reference Sales Order",
        readonly=True,
        help="Reference to the original sales order"
    )
    # New field: Similar BOM - to copy BOM from another task
    similar_bom_id = fields.Many2one(
        'project.task',
        string="Similar BOM",
        domain="[('sale_bom_ids', '!=', False), ('id', '!=', id)]",
        help="Select a task to copy its BOM structure"
    )
    # Custom display name combining product name and reference sales order
    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True,
        help="Display name combining product name and reference sales order"
    )
    hour_cost = fields.Float(string="Hour Cost",compute='_compute_hour_cost', store=True)

    over_head_cost = fields.Float(string="Over Head Cost Cost", compute="_compute_over_head_cost", store=True)
    margin_amount = fields.Float(string="Margin Amount", compute="_compute_margin_amount", store=True)
    margin_amount_with_qty = fields.Float(string="Margin Amount With Quantity", compute="_compute_margin_amount_with_qty", store=True)

    component_cost = fields.Float(
        string="Component Cost",
        compute="_compute_component_cost",
        store=True
    )
    before_margin = fields.Float(
        string="Before Margin",
        compute="_compute_before_margin",
        store=True
    )

    before_margin_with_qty = fields.Float(
        string="Before Margin with quantity",
        compute="_compute_before_margin_with_qty",
        store=True
    )
    selling_price = fields.Float(
        string="Selling Price",
        compute="_compute_selling_price",
        store=True
    )

    # New fields for quantity-based task creation
    task_sequence = fields.Integer(string="Task Sequence", default=1,
                                   help="Sequence number for tasks created from same sale line")
    total_quantity = fields.Integer(string="Total Quantity", help="Total quantity from the original sale order line")
    selling_price_with_quantity = fields.Float(string='Selling Price With Quantity',
                                               compute='_compute_selling_price_with_quantity', store=True)

    # New fields for discount calculation
    discount_amount_on_quantity = fields.Float(
        string='Discount Amount',
        compute='_compute_discount_amount_on_quantity',
        store=True,
        help="Discount amount calculated on selling price with quantity"
    )

    final_price_after_discount = fields.Float(
        string='Final Price After Discount',
        compute='_compute_final_price_after_discount',
        store=True,
        help="Final price after applying discount to selling price with quantity"
    )

    @api.depends('product_cat','product_cat.hour_cost')
    def _compute_hour_cost(self):
        for task in self:
            task.hour_cost = task.product_cat.hour_cost if task.product_cat else 0.0

    @api.onchange('product_cat')
    def _onchange_category_id_set_hour_cost(self):
        for task in self:
            if task.product_cat:
                task.hour_cost = task.product_cat.hour_cost
            else:
                task.hour_cost = 0.0

    @api.depends('selling_price_with_quantity', 'discount')
    def _compute_discount_amount_on_quantity(self):
        """Calculate the discount amount based on selling_price_with_quantity and discount percentage."""
        for record in self:
            selling_price_qty = record.selling_price_with_quantity or 0.0
            discount_percent = record.discount or 0.0
            record.discount_amount_on_quantity = selling_price_qty * (discount_percent / 100)

    @api.depends('selling_price_with_quantity', 'discount_amount_on_quantity')
    def _compute_final_price_after_discount(self):
        """Calculate the final price after applying discount."""
        for record in self:
            selling_price_qty = record.selling_price_with_quantity or 0.0
            discount_amount = record.discount_amount_on_quantity or 0.0
            record.final_price_after_discount = selling_price_qty - discount_amount



    @api.depends('before_margin', 'margin', 'selling_price', 'quantity')
    def _compute_selling_price_with_quantity(self):
        """Compute the value of the field computed_field."""
        for record in self:
            if record.selling_price:
                record.selling_price_with_quantity = (record.selling_price * record.quantity)  or 0.0

    @api.depends('before_margin', 'margin')
    def _compute_selling_price(self):
        for task in self:
            before_margin = task.before_margin or 0.0
            margin_percent = task.margin or 0.0
            task.selling_price = (before_margin + (before_margin * margin_percent / 100))

    @api.depends('component_cost', 'over_head_cost')
    def _compute_before_margin(self):
        for task in self:
            task.before_margin = (task.component_cost or 0.0) + (task.over_head_cost or 0.0)

    @api.depends('component_cost', 'over_head_cost','quantity')
    def _compute_before_margin_with_qty(self):
        for task in self:
            task.before_margin_with_qty = ((task.component_cost or 0.0) + (task.over_head_cost or 0.0)) * task.quantity

    @api.depends('sale_bom_ids.line_total')
    def _compute_component_cost(self):
        for task in self:
            task.component_cost = sum(line.line_total for line in task.sale_bom_ids)

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None, order=None):
        args = args or []
        domain = args + ['|', ('product_name', operator, name), ('reference_sales_order', operator, name)]
        print("dassssssss", self._search(domain, limit=limit, access_rights_uid=name_get_uid), domain)
        return self._search(domain, limit=limit, access_rights_uid=name_get_uid)

    def name_get(self):
        result = []
        for task in self:
            name = task.display_name or task.name or 'Unnamed Task'
            result.append((name))
        return result

    @api.depends('before_margin', 'margin')
    def _compute_margin_amount(self):
        for task in self:
            task.margin_amount = (task.before_margin or 0.0) * (task.margin or 0.0) / 100.0

    @api.depends('before_margin', 'margin','quantity')
    def _compute_margin_amount_with_qty(self):
        for task in self:
            task.margin_amount_with_qty = ((task.before_margin or 0.0) * (task.margin or 0.0) / 100.0) * task.quantity

    @api.depends('sale_bom_ids.installation_hours', 'hour_cost','product_id.installation_hours')
    def _compute_over_head_cost(self):
        for task in self:
            total_installation_hours = sum(line.installation_hours for line in task.sale_bom_ids)
            task.over_head_cost = total_installation_hours * task.hour_cost

    # Set the rec_name to use our custom display_name
    # _rec_names_search = ['display_name']

    @api.depends('product_name', 'reference_sales_order', 'task_sequence', 'total_quantity')
    def _compute_display_name(self):
        for task in self:
            name_parts = []
            if task.product_name:
                name_parts.append(task.product_name)
            if task.reference_sales_order:
                name_parts.append(f"[{task.reference_sales_order}]")
            if task.total_quantity and task.total_quantity > 1:
                name_parts.append(f"({task.task_sequence}/{task.total_quantity})")
            task.display_name = " - ".join(name_parts) if name_parts else task.name or "New Task"

    @api.onchange('similar_bom_id')
    def _onchange_similar_bom_id(self):
        """Copy BOM lines from the selected similar BOM task"""
        if self.similar_bom_id and self.similar_bom_id.sale_bom_ids:
            # Clear existing BOM lines
            self.sale_bom_ids = [(5, 0, 0)]  # Remove all existing lines

            sorted_lines = sorted(self.similar_bom_id.sale_bom_ids, key=lambda l: l.sequence)

            # Copy BOM lines from the selected task
            new_lines = []
            for line in sorted_lines:
                new_line_vals = {
                    'product_id': line.product_id.id,
                    'vendor_price': line.vendor_price,
                    'quantity': line.quantity,
                    'vendor_partner': line.vendor_partner.id if line.vendor_partner else False,
                    'discount': line.discount,
                    'display_type': line.display_type,
                    'sequence': line.sequence,
                    'name': line.name,
                }
                new_lines.append((0, 0, new_line_vals))
            print("new linw", new_lines)

            self.sale_bom_ids = new_lines

            self.description_name = self.similar_bom_id.description_name

            # Also copy some basic information if not already set
            if not self.product_cat and self.similar_bom_id.product_cat:
                self.product_cat = self.similar_bom_id.product_cat.id

            if not self.margin:
                self.margin = self.similar_bom_id.margin

            # Reset the similar_bom_id field after copying
            self.similar_bom_id = False

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

    @api.depends('sale_bom_ids.line_total', 'sale_bom_ids.vendor_price', 'margin')
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
                'list_price': task.final_price_after_discount,
                'uom_id': task.product_uom.id,
                'uom_po_id': task.product_purchase_uom.id,
                'categ_id': task.product_cat.id,
                'description_sale': task.description_name or task.product_name,
                'description': task.description_name,

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
        self.ensure_one()

        if not self.sale_order_line_id:
            _logger.warning(f"No sale order line found for task {self.name} (ID: {self.id})")
            return False

        product_variant = self.env['product.product'].search(
            [('product_tmpl_id', '=', product_template.id)], limit=1)

        if product_variant:
            self.sale_order_line_id.write({
                'product_id': product_variant.id,
                'name': product_template.name,
                'price_unit': product_template.list_price,
            })
            _logger.info(
                f"Updated sale order line {self.sale_order_line_id.id} with new product {product_template.name}")
            return True

        return False


class SaleBOM(models.Model):
    _name = 'sale.bom'

    task_id = fields.Many2one('project.task', string="Task", ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=False)
    vendor_price = fields.Float(string="Supplier Cost", store=True)
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
    product_category = fields.Many2one(related='product_id.categ_id', depends=['product_id'])

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

    installation_hours = fields.Integer(
        string="Installation Hours",
        compute="_compute_installation_hours",
        store=True
    )

    # Add new checkbox field
    is_selected = fields.Boolean(string="Selected", default=False, help="Check this box to select this BOM line")

    discounted_price = fields.Float(string='Discounted price', compute='_compute_discounted_price', store=True)



    @api.depends('product_id','product_id.installation_hours')
    def _compute_installation_hours(self):
        for record in self:
            record.installation_hours = record.product_id.product_tmpl_id.installation_hours or 0

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

    @api.onchange('product_id', 'task_id')
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
            record.installation_hours = record.product_id.product_tmpl_id.installation_hours or 0

            # Set the first vendor if available
            if sellers:
                record.vendor_partner = sellers[0].id
                record.vendor_price = sellers[0].price

                # Set the name from the product if it's empty
                if not record.name:
                    record.name = record.product_id.description_sale
            else:
                # If no vendors, set price from product standard price
                # record.vendor_price = record.product_id.standard_price
                record.name = record.product_id.description_sale

    @api.onchange('discounted_price')
    def _onchange_discount(self):
        """Update the vendor price based on the discount percentage."""
        if self.vendor_price and self.discounted_price:
            self.vendor_price = self.discounted_price
        elif not self.discounted_price:
            if self.vendor_partner:
                self.vendor_price = self.vendor_partner.price

    @api.onchange('vendor_partner')
    def _onchange_vendor_partner(self):
        """Update vendor price based on selected vendor."""
        if self.vendor_partner:
            self.vendor_price = self.vendor_partner.price  # Fill vendor_price with the selected vendor's price
        # else:
        #     self.vendor_price = 0.0  # Reset if no vendor is selected

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
            # else:
            #     record.vendor_price = record.product_id.standard_price

            if not record.name:
                record.name = record.product_id.description_sale

    @api.depends('vendor_price', 'discount')
    def _compute_discounted_price(self):
        for record in self:
            if record.discount:
                record.discounted_price = record.vendor_price * ( record.discount / 100)
            else:
                record.discounted_price =  self.vendor_partner.price

    # @api.depends('vendor_partner')
    # def _compute_vendor_price(self):
    #     for record in self:
    #         record.vendor_price = record.vendor_partner.price if record.vendor_partner else 0.0

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

            if record.product_id:
                if allowed_companies and len(allowed_companies) > 1:
                    for company in allowed_companies:
                        stock_quant = record.env['stock.quant'].sudo().search(
                            [('product_id', '=', record.product_id.id),
                             ('company_id', '=', company)],

                        )
                        for quant in stock_quant:
                            if quant.quantity > 0.0:
                                record.available_qty += quant.quantity if quant.quantity else 0.0
                else:
                    stock_quant = record.env['stock.quant'].search(
                        [('product_id', '=', record.product_id.id), ('company_id', '=', self.env.company.id)
                         ],
                    )
                    for quant in stock_quant:
                        if quant.quantity > 0.0:
                            record.available_qty += quant.quantity if quant.quantity else 0.0
            else:
                record.available_qty = 0.0
