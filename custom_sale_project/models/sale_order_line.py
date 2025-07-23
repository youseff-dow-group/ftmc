from odoo import models, fields, api


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    discount_value = fields.Float(string='Discount Amount')

    discount_amount = fields.Float(string="Discount Amount", compute="_compute_discount_amount", store=True)

    task_ids = fields.One2many('project.task', 'sale_order_line_id', string="Related Tasks")
    task_count = fields.Integer(string="Task Count", compute="_compute_task_count")

    @api.depends('task_ids')
    def _compute_task_count(self):
        for line in self:
            line.task_count = len(line.task_ids)

    @api.depends('product_uom_qty', 'price_unit', 'discount_value','discount')
    def _compute_discount_amount(self):
        for line in self:
            line.discount_value = (line.discount / 100) * (line.price_unit * line.product_uom_qty)  if line.discount else 0

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        res.update({
            'discount_amount': self.discount_value,
        })
        return res

    @api.depends('product_id')
    def _compute_name(self):
        for line in self:
            lang = line.order_id._get_lang()
            description = line.product_id.with_context(lang=lang).description_sale
            line.name = description or ''

    def action_view_tasks(self):
        self.ensure_one()
        return {
            'name': f'Tasks for {self.product_id.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'view_mode': 'tree,form',
            'domain': [('sale_order_line_id', '=', self.id)],
            'target': 'current',
        }
