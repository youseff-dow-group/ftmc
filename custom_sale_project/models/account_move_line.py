from odoo import models, api

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.depends('product_id')
    def _compute_name(self):
        for line in self:
            lang = line.move_id.partner_id.lang or self.env.lang
            product = line.product_id.with_context(lang=lang)
            line.name = product.description_sale or ''
