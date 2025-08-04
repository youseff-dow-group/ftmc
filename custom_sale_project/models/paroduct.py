from odoo import models, fields,api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    installation_hours = fields.Integer(string="Installation Hours")
    brand_id = fields.Many2one('product.brand', string="Brand")
    default_code = fields.Char(
        string='Ref No'
    )



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

    def _compute_display_name(self):
        result = []
        for rec in self:
            name = f"[{rec.default_code}] {rec.name}"
            if rec.product_tmpl_id.brand_id:
                name += f" [{rec.product_tmpl_id.brand_id.name}]"
            result.append((rec.id, name))
            rec.display_name=name



class ProductCategory(models.Model):
    _inherit = 'product.category'

    hour_cost = fields.Float(string="Hour Cost")
