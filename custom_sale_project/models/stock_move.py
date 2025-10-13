from odoo import models, fields, api


class StockMove(models.Model):
    _inherit = 'stock.move'

    delivery_price_unit = fields.Float(
        string="Price Unit",
        help="Custom price per unit for this delivery line. Used when creating an invoice from this delivery order."
    )

    # 🧮 Weight fields
    actual_weight = fields.Float(
        string="Actual Weight",
        compute="_compute_actual_weight",
        store=True,
        help="Computed automatically as product weight × quantity done."
    )
    net_weight = fields.Float(
        string="Net Weight",
        help="Editable weight value; defaults to the actual weight but can be adjusted manually."
    )
    gross_weight = fields.Float(
        string="Gross Weight",
        help="Manually entered gross weight of the line (includes packaging, etc)."
    )

    # 🗒️ Additional fields
    remarks = fields.Char(
        string="Remarks",
        help="Optional remarks or delivery notes for this line."
    )

    # 🌍 Country of origin (many2many)
    country_of_origin_ids = fields.Many2many(
        'res.country',
        'stock_move_country_rel',
        'move_id', 'country_id',
        string="Country of Origin",
        help="Select one or more countries of origin for this product."
    )

    # ⚖️ Product weight (from product)
    product_weight = fields.Float(
        string="Product Weight",
        related="product_id.weight",
        store=True,
        readonly=True,
        help="Weight of the product as defined in the product master."
    )

    related_component_id = fields.Many2one(
        'product.product',
        string="Related Component",
        domain="[('id', 'in', available_component_ids)]",
        help="Select a related component from the raw materials used in this Manufacturing Order."
    )

    available_component_ids = fields.Many2many(
        'product.product',
        compute='_compute_available_component_ids',
        store=False
    )

    @api.depends('production_id', 'raw_material_production_id')
    def _compute_available_component_ids(self):
        """Compute available raw material products for use in the domain."""
        for move in self:
            production = move.production_id or move.raw_material_production_id
            if production:
                # Collect all component products from move_raw_ids
                component_products = production.move_raw_ids.mapped('product_id')
                move.available_component_ids = component_products
            else:
                move.available_component_ids = self.env['product.product']

    # --- COMPUTE METHODS ---
    @api.depends('product_id', 'quantity')
    def _compute_actual_weight(self):
        """
        Compute Actual Weight = Product Weight × Quantity Done (or Ordered Qty if none done).
        """
        for move in self:
            qty = move.quantity or 0.0
            move.actual_weight = (move.product_id.weight or 0.0) * qty

            # Initialize net weight with actual weight if not yet set
            if not move.net_weight:
                move.net_weight = move.actual_weight
