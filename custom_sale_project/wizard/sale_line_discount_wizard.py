from odoo import models, fields, api, _
from odoo.exceptions import UserError

class SaleLineDiscountWizard(models.TransientModel):
    _name = 'sale.line.discount.wizard'
    _description = 'Sale Line Discount Wizard'

    sale_line_id = fields.Many2one('sale.order.line', string='Sale Order Line', required=True)
    discount_amount = fields.Float(string='Discount Amount (%)', required=True, help="Discount percentage to apply to all related Boms")
    
    # Display fields for information
    related_tasks_count = fields.Integer(string='Related Tasks', compute='_compute_related_tasks_count')
    current_tasks_info = fields.Text(string='Current Boms', compute='_compute_current_tasks_info')

    @api.depends('sale_line_id')
    def _compute_related_tasks_count(self):
        for wizard in self:
            if wizard.sale_line_id:
                tasks = self.env['project.task'].search([
                    ('sale_order_line_id', '=', wizard.sale_line_id.id)
                ])
                wizard.related_tasks_count = len(tasks)
            else:
                wizard.related_tasks_count = 0

    @api.depends('sale_line_id')
    def _compute_current_tasks_info(self):
        for wizard in self:
            if wizard.sale_line_id:
                tasks = self.env['project.task'].search([
                    ('sale_order_line_id', '=', wizard.sale_line_id.id)
                ])
                info_lines = []
                for task in tasks:
                    info_lines.append(f"• {task.name} - Current Discount: {task.discount}%")
                wizard.current_tasks_info = '\n'.join(info_lines) if info_lines else 'No tasks found'
            else:
                wizard.current_tasks_info = ''

    def action_apply_discount(self):
        """Apply discount to all related tasks"""
        if not self.sale_line_id:
            raise UserError(_("Sale order line is required"))
        
        if self.discount_amount < 0 or self.discount_amount > 100:
            raise UserError(_("Discount amount must be between 0 and 100"))

        # Find all tasks related to this sale order line
        tasks = self.env['project.task'].search([
            ('sale_order_line_id', '=', self.sale_line_id.id)
        ])

        if not tasks:
            raise UserError(_("No Boms found for this sale order line"))


        print("dissssssssss", self.discount_amount * 100)

        # Update discount for all related tasks
        tasks.write({'discount': self.discount_amount * 100})

        # Show success message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Discount of %s%% has been applied to %d boms') % (self.discount_amount, len(tasks)),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},

            }
        }

    def action_cancel(self):
        """Cancel the wizard"""
        return {'type': 'ir.actions.act_window_close'}
