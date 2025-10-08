from odoo import models, fields


class StockMove(models.Model):
    _inherit = 'stock.move'

    delivery_price_unit = fields.Float(
        string="Price Unit",
        help="Custom price per unit for this delivery line. Used when creating an invoice from this delivery order."
    )
