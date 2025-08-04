from odoo import models, api
from odoo.tools import get_lang

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.depends('product_qty', 'product_uom', 'company_id')
    def _compute_price_unit_and_date_planned_and_name(self):
        super()._compute_price_unit_and_date_planned_and_name()

        for line in self:
            if not line.product_id:
                continue

            # 👇 Replace name with sales_description
            lang = get_lang(line.env, line.partner_id.lang).code
            product = line.product_id.with_context(lang=lang)
            line.name = product.description_sale or ''
