from odoo import models, fields, api


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    related_component_id = fields.Many2one(
        'product.product',
        string="Related Component",
        domain="[('id', 'in', available_component_ids)]",
        help="Select a component that already exists in the Components section."
    )

    available_component_ids = fields.Many2many(
        'product.product',
        compute='_compute_available_component_ids',
        store=False
    )

    @api.depends('move_raw_ids')
    def _compute_available_component_ids(self):
        """Compute all available raw material products for domain."""
        for production in self:
            component_products = production.move_raw_ids.mapped('product_id')
            production.available_component_ids = component_products
