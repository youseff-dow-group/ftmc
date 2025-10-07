from odoo import models, fields, api

from odoo.exceptions import ValidationError



class MrpBom(models.Model):
    _inherit = 'mrp.bom'



    # Fields specifying custom line logic
    display_type = fields.Selection(
        selection=[
            ('line_section', "Section"),
            ('line_note', "Note"),
        ],
        default=False)

    name = fields.Text(
        string="Description",
        readonly=False)

    sale_order_id = fields.Many2one('sale.order', string='Sale Order')

    # Smart button for viewing the product
    def action_view_sale_order(self):
        """Action to open the Sale Order form view"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sale Order',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'current',
        }


class MrpBom(models.Model):
    _inherit = 'mrp.bom.line'

    product_id = fields.Many2one('product.product', 'Component', required=False)
    product_uom_id = fields.Many2one(
        'uom.uom', 'Product Unit of Measure',required=False,
    )

    # Fields specifying custom line logic
    display_type = fields.Selection(
        selection=[
            ('line_section', "Section"),
            ('line_note', "Note"),
        ],
        default=False)

    name = fields.Text(
        string="Description",
        readonly=False)