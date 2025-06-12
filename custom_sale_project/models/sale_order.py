from odoo import models, fields, api

from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    project_id = fields.Many2one('project.project', string="Related Project")
    task_count = fields.Integer(string="Tasks Count", compute="_compute_task_count")

    def _compute_task_count(self):
        for order in self:
            order.task_count = self.env['project.task'].search_count(
                [('project_id', '=', order.project_id.id)]) if order.project_id else 0

    def action_create_sale_project(self):
        for sale in self:
            if not sale.order_line:
                raise ValidationError(
                    "Ensure Order lines are filled")

            project = self.env['project.project'].create({
                'name': f"{sale.name} - {sale.partner_id.name}",  # Fixed: use sale instead of self
            })
            sale.project_id = project.id

            for line in sale.order_line:
                # Skip lines without products
                if not line.product_id:
                    continue

                # Get the product template from the product variant
                product_template = line.product_id.product_tmpl_id

                project_task = self.env['project.task'].create({
                    'name': line.product_id.name,  # Task name = Product name
                    'project_id': project.id,
                    'product_id': product_template.id,  # Pass the product template ID
                    'reference_sales_order': sale.name,  # Set the reference sales order field

                })

                # Update the sale order line with reference to the task
                project_task.sale_order_id=sale.id
                line.task_id = project_task.id

    # def action_create_sale_project(self):
    #     for sale in self:
    #         if not sale.order_line:
    #             raise ValidationError(
    #                 "Ensure Order lines are filled")
    #
    #         project = self.env['project.project'].create({
    #             'name': f"{self.name} - {self.partner_id.name}",  # Properly formatted string
    #         })
    #         sale.project_id = project.id
    #
    #         for line in sale.order_line:
    #             project_task = self.env['project.task'].create({
    #                 'name': line.product_id.name,  # Task name = Product name
    #                 'project_id': project.id,
    #
    #             })
    #             project_task.sale_order_id=sale.id
    #             line.task_id = project_task.id

    def action_view_project(self):
        self.ensure_one()
        return {
            'name': 'Project',
            'type': 'ir.actions.act_window',
            'res_model': 'project.project',
            'view_mode': 'form',
            'res_id': self.project_id.id,
            'target': 'current',
        }

    def action_view_tasks(self):
        self.ensure_one()
        return {
            'name': 'Tasks',
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'view_mode': 'tree,form',
            'domain': [('project_id', '=', self.project_id.id)],
            'target': 'current',
        }


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    discount_value = fields.Float(string='Discount Amount')

    discount_amount = fields.Float(string="Discount Amount", compute="_compute_discount_amount", store=True)

    task_id = fields.Many2one('project.task', string="Related Tasks")

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id', 'discount_value')
    def _compute_discount_amount(self):
        for line in self:
            line.discount = (line.discount_value / line.price_unit) * 100 if line.discount_value else 0

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        res.update({
            'discount_amount': self.discount_value,
        })
        return res
