from odoo import models, fields, api

from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_create_sale_project(self):
        for sale in self:
            if not sale.order_line :
                raise ValidationError(
                    "Ensure Order lines are filled")

            project = self.env['project.project'].create({
                    'name': f"{self.name} - {self.partner_id.name}", 
            })

            for line in sale.order_line:
                self.env['project.task'].create({
                    'name': line.product_id.name,  
                    'project_id': project.id,
                })


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    discount_value = fields.Float(string='Discount Amount')

    discount_amount = fields.Float(string="Discount Amount",compute="_compute_discount_amount",store=True)

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id','discount_value')
    def _compute_discount_amount(self):
        for line in self:
            line.discount=(line.discount_value / line.price_unit ) * 100 if line.discount_value else 0

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        res.update({
            'discount_amount': self.discount_value,
        })
        return res

