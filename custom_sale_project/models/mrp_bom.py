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