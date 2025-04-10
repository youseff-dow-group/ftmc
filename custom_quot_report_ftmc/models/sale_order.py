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


class CategoryMakeRelation(models.Model):
    _name = 'category.make.relation'
    _description = 'Product Category and Component Make Relation'

    sale_id = fields.Many2one('sale.order', string='Sale Order', ondelete='cascade')
    category_id = fields.Many2one('product.category', string='Product Category', required=True)
    make_ids = fields.Many2many('component.make', string='Component Makes', required=True)


    category_name = fields.Char(related='category_id.name', string='Category Name', readonly=True)
