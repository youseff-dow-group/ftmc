from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    installation_hours = fields.Integer(string="Installation Hours")
    brand_id = fields.Many2one('product.brand', string="Brand")
    default_code = fields.Char(
        string='Ref No'
    )
    product_name_arabic = fields.Char(string='Product Name Arabic')
    sales_details_arabic = fields.Char(string='Sales Description Arabic')


    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        if name:
            # Search for brand first
            brand_products = self.search([('brand_id.name', operator, name)], limit=limit)
            if brand_products:
                return brand_products.name_get()

            # Or include brand in main search domain
            domain = ['|', '|', '|','|', ('brand_id.name', operator, name),
                      ('name', operator, name), ('description_sale', operator, name), ('default_code', operator, name),('catalogue_number', operator, name)]
            products = self.search(domain + args, limit=limit)
            return products.name_get()

        return super().name_search(name=name, args=args, operator=operator, limit=limit)


class Productproduct(models.Model):
    _inherit = 'product.product'

    installation_hours = fields.Integer(
        string="Installation Hours",
        related='product_tmpl_id.installation_hours',
        store=True,
        readonly=False
    )
    brand_id = fields.Many2one(related='product_tmpl_id.brand_id', string="Brand", store=True, readonly=False)
    default_code = fields.Char(
        string='Ref No'
    )
    product_name_arabic = fields.Char(string='Product Name Arabic')
    sales_details_arabic = fields.Char(string='Sales Description Arabic')


    def _compute_display_name(self):
        result = []
        for rec in self:
            name = f"[{rec.default_code}] {rec.name}"
            if rec.product_tmpl_id.brand_id:
                name += f" [{rec.product_tmpl_id.brand_id.name}]"
            result.append((rec.id, name))
            rec.display_name = name

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        if name:
            # Search for brand first
            brand_products = self.search([('brand_id.name', operator, name)], limit=limit)
            if brand_products:
                return brand_products.name_get()

            domain = ['|', '|', '|', '|', ('brand_id.name', operator, name),
                      ('name', operator, name), ('description_sale', operator, name), ('default_code', operator, name),
                      ('catalogue_number', operator, name)]
            products = self.search(domain + args, limit=limit)
            return products.name_get()

        return super().name_search(name=name, args=args, operator=operator, limit=limit)


class ProductCategory(models.Model):
    _inherit = 'product.category'

    hour_cost = fields.Float(string="Hour Cost")
