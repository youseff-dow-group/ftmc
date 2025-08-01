from odoo import models, fields, api ,_

from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'


    project_id = fields.Many2one('project.project', string="Related Project")
    task_count = fields.Integer(string="Tasks Count", compute="_compute_task_count")

    total_discount = fields.Float(string='Total Discount', compute='_compute_total_discount', store=True)

    @api.depends('order_line.discount_value','order_line.discount')
    def _compute_total_discount(self):
        """Compute the value of the field total_discount."""
        for record in self:
            total_discount = sum(
                line.discount_value
                for line in record.order_line
            )
            record.total_discount = total_discount

    def _compute_task_count(self):
        for order in self:
            order.task_count = self.env['project.task'].search_count(
                [('project_id', '=', order.project_id.id)]) if order.project_id else 0

    def action_create_sale_project(self):
        for sale in self:
            if not sale.order_line:
                raise ValidationError("Ensure Order lines are filled")

            project = self.env['project.project'].create({
                'name': f"{sale.name} - {sale.partner_id.name}",
            })
            sale.project_id = project.id

            for line in sale.order_line:
                # Skip lines without products
                if not line.product_id:
                    continue

                # Get the product template from the product variant
                product_template = line.product_id.product_tmpl_id

                # Create tasks based on quantity
                quantity = int(line.product_uom_qty) if line.product_uom_qty > 0 else 1

                for i in range(quantity, 0, -1):
                    # Create task name with sequence number if quantity > 1
                    task_name = f"{line.product_id.name} - {i}" if quantity > 1 else line.product_id.name

                    project_task = self.env['project.task'].create({
                        'name': task_name,
                        'project_id': project.id,
                        'product_id': product_template.id,
                        'reference_sales_order': sale.name,
                        'sale_order_id': sale.id,
                        'sale_order_line_id': line.id,  # Link to specific sale order line
                        'task_sequence': i + 1,  # Add sequence number for tracking
                        'total_quantity': quantity,  # Store total quantity for reference
                    })
                    project_task.sale_order_id = sale.id
                    project_task.sale_order_line_id = line.id


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

    def action_update_lines_from_tasks(self):
        """Update sale order lines based on related tasks quantities and selling prices"""
        for sale in self:
            if not sale.project_id:
                raise ValidationError("No project found. Please create a project first.")

            for line in sale.order_line:
                # Skip lines without products
                if not line.product_id:
                    continue

                # Find all tasks related to this sale order line
                related_tasks = self.env['project.task'].search([
                    ('sale_order_line_id', '=', line.id)
                ])

                if related_tasks:
                    # Update quantity based on number of tasks
                    task_count = len(related_tasks)
                    total_quantity = sum(task.quantity for task in related_tasks if task.quantity > 0)

                    line.product_uom_qty = total_quantity
                    # print("totaaaaaala ", total_quantity)

                    # Calculate average selling price from tasks
                    total_selling_price = sum(task.final_price_after_discount for task in related_tasks if task.final_price_after_discount > 0)

                    if total_selling_price > 0:
                        average_price = total_selling_price / total_quantity
                        line.price_unit = average_price
                    else:
                        # If no selling price in tasks, keep original price
                        pass

            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }

