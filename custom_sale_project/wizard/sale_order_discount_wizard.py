from odoo import models, fields, api, _
from odoo.exceptions import UserError

class SaleOrderDiscountWizard(models.TransientModel):
    _name = 'sale.order.discount.wizard'
    _description = 'Sale Order Discount Wizard'

    sale_order_id = fields.Many2one('sale.order', string='Sale Order', required=True)
    discount_amount = fields.Float(string='Discount Amount (%)', required=True, help="Discount percentage to apply")
    product_category_id = fields.Many2one('product.category', string='Product Category', required=True, help="Category to apply discount to")
    
    # Display fields for information
    affected_bom_lines_count = fields.Integer(string='Affected BOM Lines', compute='_compute_affected_bom_lines')
    current_bom_info = fields.Text(string='BOM Lines to be Updated', compute='_compute_current_bom_info')

    @api.depends('sale_order_id', 'product_category_id')
    def _compute_affected_bom_lines(self):
        for wizard in self:
            if wizard.sale_order_id and wizard.product_category_id:
                # Find all BOM lines in tasks related to this sale order with the specified category
                bom_lines = self._get_affected_bom_lines()
                wizard.affected_bom_lines_count = len(bom_lines)
            else:
                wizard.affected_bom_lines_count = 0

    @api.depends('sale_order_id', 'product_category_id')
    def _compute_current_bom_info(self):
        for wizard in self:
            if wizard.sale_order_id and wizard.product_category_id:
                bom_lines = self._get_affected_bom_lines()
                info_lines = []
                for bom_line in bom_lines:
                    task_name = bom_line.task_id.name if bom_line.task_id else 'Unknown Task'
                    product_name = bom_line.product_id.name if bom_line.product_id else 'Unknown Product'
                    current_discount = getattr(bom_line, 'discount', 0)
                    info_lines.append(f"• {task_name} - {product_name} - Current Discount: {current_discount}%")
                wizard.current_bom_info = '\n'.join(info_lines) if info_lines else 'No BOM lines found for this category'
            else:
                wizard.current_bom_info = ''

    def _get_affected_bom_lines(self):
        """Get all BOM lines that will be affected by the discount"""
        if not self.sale_order_id or not self.product_category_id:
            return self.env['sale.bom']

        # Find all tasks related to this sale order
        tasks = self.env['project.task'].search([
            ('sale_order_id', '=', self.sale_order_id.id)
        ])

        # Find all BOM lines in these tasks with the specified product category
        bom_lines = self.env['sale.bom'].search([
            ('task_id', 'in', tasks.ids),
            ('product_id.categ_id', '=', self.product_category_id.id)
        ])

        return bom_lines

    def action_apply_discount(self):
        """Apply discount to all BOM lines with the specified category"""
        if not self.sale_order_id:
            raise UserError(_("Sale order is required"))
        
        if not self.product_category_id:
            raise UserError(_("Product category is required"))
        
        if self.discount_amount < 0 or self.discount_amount > 100:
            raise UserError(_("Discount amount must be between 0 and 100"))

        # Get affected BOM lines
        bom_lines = self._get_affected_bom_lines()

        if not bom_lines:
            raise UserError(_("No BOM lines found for category '%s' in this sale order") % self.product_category_id.name)

        # Update discount for all affected BOM lines
        bom_lines.write({'discount': self.discount_amount})

        # Show success message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Discount of %s%% has been applied to %d BOM lines in category "%s"') % (
                    self.discount_amount, len(bom_lines), self.product_category_id.name),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},

            }
        }

    def action_cancel(self):
        """Cancel the wizard"""
        return {'type': 'ir.actions.act_window_close'}
