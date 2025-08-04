from odoo import models, fields, api, _
from odoo.exceptions import UserError

class SaleLineMarginWizard(models.TransientModel):
    _name = 'sale.line.margin.wizard'
    _description = 'Sale Line Margin Wizard'

    sale_line_id = fields.Many2one('sale.order.line', string='Sale Order Line', required=True)
    margin_amount = fields.Float(string='Margin Amount (%)', required=True, help="Margin percentage to apply to all related tasks")
    
    # Display fields for information
    related_tasks_count = fields.Integer(string='Related Tasks', compute='_compute_related_tasks_count')
    current_tasks_info = fields.Text(string='Current Tasks', compute='_compute_current_tasks_info')

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
                    info_lines.append(f"• {task.name} - Current Margin: {task.margin}%")
                wizard.current_tasks_info = '\n'.join(info_lines) if info_lines else 'No tasks found'
            else:
                wizard.current_tasks_info = ''

    def action_apply_margin(self):
        """Apply margin to all related tasks"""
        if not self.sale_line_id:
            raise UserError(_("Sale order line is required"))
        
        if self.margin_amount < 0:
            raise UserError(_("Margin amount cannot be negative"))

        # Find all tasks related to this sale order line
        tasks = self.env['project.task'].search([
            ('sale_order_line_id', '=', self.sale_line_id.id)
        ])

        if not tasks:
            raise UserError(_("No tasks found for this sale order line"))

        # Update margin for all related tasks
        tasks.write({'margin': self.margin_amount})

        # Show success message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Margin of %s%% has been applied to %d tasks') % (self.margin_amount, len(tasks)),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},

            }
        }

    def action_cancel(self):
        """Cancel the wizard"""
        return {'type': 'ir.actions.act_window_close'}
