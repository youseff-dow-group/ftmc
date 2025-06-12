from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    installation_hours = fields.Integer(string="Installation Hours")


class Productproduct(models.Model):

    _inherit = 'product.product'

    installation_hours = fields.Integer(string="Installation Hours")
