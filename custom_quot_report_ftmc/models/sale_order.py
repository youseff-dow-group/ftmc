from odoo import models, fields, api
from collections import defaultdict

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    quoted_to = fields.Char(string='Quoted To')
    prepared_by = fields.Char(string='Prepared By')
    attention = fields.Char(string='Attention')
    project_name = fields.Char(string='Project Name')
    inquiry_num = fields.Char(string='Inquiry Number')

    category_make_ids = fields.One2many('category.make.relation', 'sale_id', string='Category Makes')


    def get_product_categories(self):
        """
        Group order lines by product category and return a dictionary
        with category names as keys and lists of order lines as values
        """
        categories = defaultdict(list)

        for line in self.order_line:
            category_name = line.product_id.categ_id.name or "Uncategorized"
            categories[category_name].append(line)

        return categories

    def get_category_summary(self):
        """
        Calculate total quantity and amount for each product category
        Returns a list of dictionaries with category name, total quantity, and total amount
        """
        summary = []
        categories = self.get_product_categories()

        for category_name, lines in categories.items():
            total_qty = sum(line.product_uom_qty for line in lines)
            total_amount = sum(line.price_subtotal for line in lines)

            summary.append({
                'name': category_name,
                'qty': total_qty,
                'amount': total_amount
            })

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
