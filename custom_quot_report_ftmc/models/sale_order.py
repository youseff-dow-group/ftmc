from odoo import models, fields, api
from collections import defaultdict
from odoo.exceptions import UserError, ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    prepared_by = fields.Many2one('hr.employee',string='Prepared By')
    project_name = fields.Char(string='Project Name')
    inquiry_date  = fields.Date(string="Inquiry Date ")
    origin = fields.Char(
        string="Inquiry Number",
        help="Reference of the document that generated this sales order request"
    )

    opportunity_id = fields.Many2one(
        'crm.lead', string='Opportunity / Project', check_company=True,
        domain="[('type', '=', 'opportunity'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    contact_ids = fields.Many2many(
        'res.partner',
        string="Contacts",
        domain="[('parent_id', '=', partner_id)]"
    )

    category_make_ids = fields.One2many('category.make.relation', 'sale_id', string='Category Makes')

    def get_product_tasks(self):
        """
        Group tasks by sale order lines.
        Returns a list of dictionaries with 'line' and its related 'tasks'.
        """
        summary = []
        categories = self.get_product_orderlines()
        print("iteeeeeesm ", categories.items())
        for category_name, entries in categories.items():
            for entry in entries:
                tasks = entry['tasks']
                print("tasks", tasks)

                for task in tasks:
                    print("task111111111111", task)
                    summary.append({
                        'name': task.description_name,
                        'unit_price': task.selling_price,
                        'total': task.selling_price_with_quantity
                    })

        return summary

    def get_product_orderlines(self):
        """
        Group order lines by product category.
        Each value is a list of dictionaries with:
        - 'lines': the sale order line
        - 'tasks': list of summarized task info (dicts)
        """
        categories = defaultdict(list)

        for line in self.order_line:
            category_name = line.product_template_id.name or "Uncategorized"

            # Build task summaries
            task_summaries = []
            for task in line.task_ids:
                task_summaries.append({
                    'name': task.description_name or '',
                    'quantity': task.quantity or 0.0,
                    'unit_price': task.selling_price or 0.0,
                    'total_price': task.selling_price_with_quantity or 0.0,
                    'total': sum(task.quantity for task in line.task_ids) or 0.0,
                })

            # Append to category
            categories[category_name].append({
                'lines': line,
                'tasks': task_summaries,
            })

        return categories



    def get_category_summary(self):
        """
        Calculate total quantity and amount for each product category
        Returns a list of dictionaries with category name, total quantity, and total amount
        """
        summary = []
        categories = self.get_product_orderlines()
        print("iteeeeeesm ", categories.items())
        for category_name, entries in categories.items():
            for entry in entries:
                lines = entry['lines']

                total_qty = sum(line.product_uom_qty for line in lines)
                total_amount = sum(line.price_subtotal for line in lines)

                summary.append({
                    'name': category_name,
                    'qty': total_qty,
                    'amount': total_amount
                })
                print("line", lines)

        return summary

    def get_category_makes(self):
        """
        Get the component makes for each product category in the sale order
        Returns a dictionary with category names as keys and lists of make names as values
        """
        result = {}
        for relation in self.category_make_ids:
            make_names = [make.name for make in relation.make_ids]
            if make_names:  # Only add if there are makes
                result[relation.category_id.name] = make_names
        return result

    def get_category_makes_with_descriptions(self):
        """
        Get the component makes with descriptions for each product category in the sale order
        Returns a dictionary with category names as keys and lists of make details as values
        """
        result = {}
        for relation in self.category_make_ids:
            make_details = []
            for make in relation.make_ids:
                make_details.append({
                    'name': make.name,
                    'description': make.description or make.name  # Use name if description is empty
                })
            if make_details:  # Only add if there are makes
                result[relation.category_id.name] = make_details
        return result

    def update_category_make_relations(self):
        """
        Update category_make_ids based on product categories in order lines
        """
        # Get all unique product categories from order lines
        categories = set()
        for line in self.order_line:
            if line.product_id and line.product_id.categ_id:
                categories.add(line.product_id.categ_id.id)

        existing_categories = set(relation.category_id.id for relation in self.category_make_ids)

        for category_id in categories:
            if category_id not in existing_categories:
                self.env['category.make.relation'].create({
                    'sale_id': self.id,
                    'category_id': category_id,
                    # Default make_ids will be required to be filled by the user
                })

    def write(self, vals):
        """Override write method to update category_make_relations when order lines change"""
        res = super(SaleOrder, self).write(vals)
        if 'order_line' in vals:
            self.update_category_make_relations()
        return res

    def get_mdb_products(self):
        """
        Get products that are Main Distribution Boards (MDBs).
        Returns a list of products (one per sale order line) with their related tasks.
        """
        mdb_products = []

        for line in self.order_line:
            if not line.product_id:
                continue

            # Get tasks only related to this line
            task_summaries = []
            for task in line.task_ids:
                task_summaries.append({
                    'id': task.id,
                    'name': task.description_name or '',
                    'quantity': task.quantity or 0.0,
                })

            mdb_products.append({
                'product': line.product_id,
                'qty': line.product_uom_qty,
                'line': line,
                'tasks': task_summaries,
            })

        print("mddddddddddddddddddb", mdb_products)
        return mdb_products
    def get_product_bom(self, product_id):
        """
        Get the Bill of Materials for a product
        Returns the BOM record for the given product
        """
        BOM = self.env['mrp.bom']
        bom = BOM.sudo().search([
            ('product_tmpl_id', '=', product_id.product_tmpl_id.id),
            ('type', '=', 'normal')
        ], limit=1)

        return bom

    def get_bom_components_by_category(self, product_id,so_line_qty):
        """
        Get BOM components grouped by category for a product
        Returns a dictionary with category names as keys and lists of components as values
        """


        bom = self.get_product_bom(product_id)
        if not bom:
            return {}

        components_by_category = defaultdict(list)

        bom_qty = bom.product_qty or 1.0


        for line in bom.bom_line_ids:
            component = line.product_id
            category_name = component.categ_id.name or ("Note" if line.display_type else "Uncategorized")
            component_qty = (so_line_qty * line.product_qty) / bom_qty

            components_by_category[category_name].append({
                'product': component,
                'qty': component_qty,
                'uom': line.product_uom_id.name,
                'name': line.name
            })

        return components_by_category

    def get_total_products_qty(self):
        """
        Calculate the total quantity of products in the sale order
        """
        return sum(line.product_uom_qty for line in self.order_line)

    @api.model
    def get_task_bom_details(self, task_id):
        """
        Get BOM details for a specific task by task_id.
        Returns a list of key-value dictionaries for each BOM line.
        """
        task = self.env['project.task'].browse(task_id)
        if not task.exists():
            raise ValidationError(f"Task with ID {task_id} not found.")

        result = []
        # Sort sale_bom_ids by 'sequence'
        sorted_bom_lines = task.sale_bom_ids.sorted('sequence')

        for bom_line in sorted_bom_lines:
            result.append({
                'product': bom_line.name,
                'quantity': bom_line.quantity,
            })
        print("resasasasasas------", result)

        return result


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.model
    def create(self, vals):
        """Override create method to update category_make_relations when a new line is created"""
        line = super(SaleOrderLine, self).create(vals)
        if line.order_id:
            line.order_id.update_category_make_relations()
        return line

    def write(self, vals):
        """Override write method to update category_make_relations when a line is modified"""
        res = super(SaleOrderLine, self).write(vals)
        if 'product_id' in vals and self:
            for line in self:
                if line.order_id:
                    line.order_id.update_category_make_relations()
        return res


class CategoryMakeRelation(models.Model):
    _name = 'category.make.relation'
    _description = 'Product Category and Component Make Relation'

    sale_id = fields.Many2one('sale.order', string='Sale Order', ondelete='cascade')
    category_id = fields.Many2one('product.category', string='Product Category', required=True)
    make_ids = fields.Many2many('component.make', string='Component Makes', required=True)


    category_name = fields.Char(related='category_id.name', string='Category Name', readonly=True)
