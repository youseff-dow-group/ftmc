from odoo import models, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('product_id')
    def _compute_name(self):
        for line in self:
            lang = line.order_id._get_lang()
            description = line.product_id.with_context(lang=lang).description_sale
            line.name = description or ''
