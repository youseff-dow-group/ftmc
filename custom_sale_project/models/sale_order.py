from odoo import models, fields, api, _

from odoo.exceptions import ValidationError
import xlsxwriter
import base64
from io import BytesIO
from datetime import datetime


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    project_id = fields.Many2one('project.project', string="Related Project")
    task_count = fields.Integer(string="Boms Count", compute="_compute_task_count")

    total_discount = fields.Float(string='Total Discount', compute='_compute_total_discount', store=True)
    # Add field to store temporary report file
    costing_report_file = fields.Binary(string='Costing Report File', attachment=False)

    @api.depends('order_line.discount_value', 'order_line.discount')
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
            'name': 'Boms',
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
                    total_selling_price = sum(task.final_price_after_discount for task in related_tasks if
                                              task.final_price_after_discount > 0)

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

    def action_create_bom_from_lines(self):
        """Create one BOM for each sale order line, using components from related tasks' BOMs."""
        for order in self:
            if not order.order_line:
                raise ValidationError(_("This Sale Order has no lines."))

            created_boms = self.env['mrp.bom']

            for line in order.order_line:
                if not line.product_id:
                    continue

                #  Prevent duplicate BOM creation for the same sale order line
                existing_bom = self.env['mrp.bom'].search([
                    ('sale_order_id', '=', order.id)
                ], limit=1)
                if existing_bom:
                    raise ValidationError(
                        _("A BOM already exists for this Sale Order Line (%s).") % line.product_id.display_name
                    )

                # 🔍 Find all related tasks with a valid BOM
                related_tasks = self.env['project.task'].search([
                    ('sale_order_line_id', '=', line.id),
                    ('bom_id', '!=', False)
                ])

                # 🚫 Skip this line if no task has a BOM
                if not related_tasks:
                    continue

                # ✅ Create a new BOM for the product in this sale order line
                new_bom = self.env['mrp.bom'].sudo().create({
                    'product_tmpl_id': line.product_id.product_tmpl_id.id,
                    'product_qty': line.product_uom_qty or 1.0,
                    'type': 'phantom',
                    'sale_order_id': order.id
                })

                # ✅ Add components from each task's BOM
                for task in related_tasks:
                    self.env['mrp.bom.line'].sudo().create({
                        'bom_id': new_bom.id,
                        'product_id': task.product_id.product_variant_id.id,
                        'product_qty': task.quantity,
                        'sequence': task.task_sequence,
                        'name': task.product_name ,
                    })

                created_boms |= new_bom

            # 🚨 If no BOM was created for any line, raise an error
            if not created_boms:
                raise ValidationError(_("No tasks with valid BOMs were found for this Sale Order."))

            # ✅ Open the last created BOM
            return {
                'type': 'ir.actions.act_window',
                'name': _('Created BOM'),
                'res_model': 'mrp.bom',
                'view_mode': 'form',
                'res_id': created_boms[-1].id,
                'target': 'current',
            }

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None, order=None):
        args = args or []
        domain = args + ['|', ('reference_sales_order', operator, name)]
        print("نننننننننننننن", self._search(domain, limit=limit, access_rights_uid=name_get_uid), domain)
        return self._search(domain, limit=limit, access_rights_uid=name_get_uid)

        # ----------------------------------------- Report Excel ---------------------------------

    def action_generate_costing_report(self):
        """Open wizard to generate costing report"""
        return {
            'name': 'Generate Costing Report',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order.costing.report',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_sale_order_id': self.id}
        }

    def action_print_costing_report(self):
        """Generate and download costing report directly"""
        # Generate the Excel file
        excel_data = self._generate_costing_excel()

        # Store it temporarily in the record
        self.costing_report_file = excel_data['file_data']

        # Return download action
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model=sale.order&id={self.id}&field=costing_report_file&filename={excel_data["filename"]}&download=true',
            'target': 'self',
        }

    def _generate_costing_excel(self):
        """Generate the Excel costing report"""
        # Create Excel file in memory
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Costing Sheet')

        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#D3D3D3',
            'border': 1
        })

        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center',
            'valign': 'vcenter',
            'border': 2
        })

        panel_header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#E6E6E6',
            'border': 1,
            'font_size': 10,
            'text_wrap': True
        })

        data_format = workbook.add_format({
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'num_format': '#,##0.00'
        })

        label_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'bold': False
        })

        total_format = workbook.add_format({
            'align': 'right',
            'valign': 'vcenter',
            'border': 2,
            'bold': True,
            'bg_color': '#F0F0F0',
            'num_format': '#,##0.00'
        })

        labor_format = workbook.add_format({
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'bold': True,
            'bg_color': '#E8F4FD',
            'num_format': '#,##0.00'
        })

        margin_format = workbook.add_format({
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'bold': True,
            'bg_color': '#FFF2CC',
            'num_format': '#,##0.00'
        })

        margin_percent_format = workbook.add_format({
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'bold': True,
            'bg_color': '#FFEB9C',
            'num_format': '0.00"%"'
        })

        # Discount formats
        discount_format = workbook.add_format({
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'bold': True,
            'bg_color': '#FFE6E6',
            'num_format': '#,##0.00'
        })

        discount_percent_format = workbook.add_format({
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'bold': True,
            'bg_color': '#FFCCCC',
            'num_format': '0.00"%"'
        })

        # Get costing data structure
        costing_data = self._get_costing_data_from_lines()

        # Get sale order lines (columns) and product categories (rows)
        sale_lines = costing_data['sale_lines']
        product_categories = costing_data['product_categories']
        data_matrix = costing_data['data_matrix']
        labor_costs = costing_data['labor_costs']
        margin_percentages = costing_data['margin_percentages']
        margin_amounts = costing_data['margin_amounts']
        discount_percentages = costing_data['discount_percentages']
        discount_amounts = costing_data['discount_amounts']

        # Calculate dynamic column count
        total_columns = len(sale_lines) + 2  # +2 for category column and total column

        # Set column widths dynamically
        worksheet.set_column('A:A', 30)  # Category column
        for i in range(1, total_columns):
            worksheet.set_column(i, i, 15)  # Data columns

        # Write header information
        header_end_col = chr(ord('A') + total_columns - 1)

        # Write title
        worksheet.merge_range(f"A3:{header_end_col}3", 'COSTING SHEET', title_format)

        # Write project info
        worksheet.merge_range(f"A5:{chr(ord('A') + 2)}5", f"Project: {self.name}", label_format)

        # Write column headers
        worksheet.write('A6', 'PANEL TYPE', panel_header_format)

        # Write sale order line headers (columns)
        for col_idx, line in enumerate(sale_lines, 1):
            # Truncate long product names for better display
            product_name = line.product_id.name[:20] + '...' if len(line.product_id.name) > 20 else line.product_id.name
            worksheet.write(5, col_idx, product_name, panel_header_format)

        # Write TOTAL header
        worksheet.write(5, len(sale_lines) + 1, 'TOTAL', panel_header_format)

        # Write data rows (product categories)
        current_row = 6
        for row_idx, category in enumerate(product_categories):
            # Write category name
            worksheet.write(current_row + row_idx, 0, category.complete_name if category else 'Uncategorized',
                            label_format)

            # Write data for each sale order line
            row_total = 0
            for col_idx, line in enumerate(sale_lines, 1):
                value = data_matrix.get(category.id if category else 0, {}).get(line.id, 0)
                if value > 0:
                    worksheet.write(current_row + row_idx, col_idx, value, data_format)
                    row_total += value
                else:
                    worksheet.write(current_row + row_idx, col_idx, '-', label_format)

            # Write row total
            if row_total > 0:
                worksheet.write(current_row + row_idx, len(sale_lines) + 1, row_total, data_format)
            else:
                worksheet.write(current_row + row_idx, len(sale_lines) + 1, '-', label_format)

        # Write LABOR row
        labor_row = current_row + len(product_categories)
        worksheet.write(labor_row, 0, 'LABOR', labor_format)

        total_labor = 0
        for col_idx, line in enumerate(sale_lines, 1):
            labor_cost = labor_costs.get(line.id, 0)
            if labor_cost > 0:
                worksheet.write(labor_row, col_idx, labor_cost, labor_format)
                total_labor += labor_cost
            else:
                worksheet.write(labor_row, col_idx, '-', labor_format)

        # Write total labor
        if total_labor > 0:
            worksheet.write(labor_row, len(sale_lines) + 1, total_labor, labor_format)
        else:
            worksheet.write(labor_row, len(sale_lines) + 1, '-', labor_format)

        # Write TOTAL COST row (using final_price_after_discount)
        totals_row = labor_row + 1
        worksheet.write(totals_row, 0, 'TOTAL COST', total_format)

        grand_total = 0
        for col_idx, line in enumerate(sale_lines, 1):
            # Calculate total categorized costs for this column
            categorized_total = 0
            for category in product_categories:
                category_id = category.id if category else 0
                categorized_total += data_matrix.get(category_id, {}).get(line.id, 0)

            # Add labor cost for this column
            labor_cost = labor_costs.get(line.id, 0)

            # Total cost = categorized costs + labor
            col_total = categorized_total + labor_cost

            if col_total > 0:
                worksheet.write(totals_row, col_idx, col_total, total_format)
                grand_total += col_total
            else:
                worksheet.write(totals_row, col_idx, '-', total_format)

        # Write grand total
        worksheet.write(totals_row, len(sale_lines) + 1, grand_total, total_format)

        # Write DISCOUNT row (percentages) - FIXED ROW POSITIONING
        discount_row = totals_row + 1
        worksheet.write(discount_row, 0, 'DISCOUNT', discount_percent_format)

        total_discount_percent = 0
        discount_count = 0
        for col_idx, line in enumerate(sale_lines, 1):
            discount_percent = discount_percentages.get(line.id, 0)
            if discount_percent > 0:
                worksheet.write(discount_row, col_idx, discount_percent / 100, discount_percent_format)
                total_discount_percent += discount_percent
                discount_count += 1
            else:
                worksheet.write(discount_row, col_idx, '-', discount_percent_format)

        # Write average discount percentage
        if discount_count > 0:
            avg_discount = total_discount_percent / 100
            worksheet.write(discount_row, len(sale_lines) + 1, avg_discount, discount_percent_format)
        else:
            worksheet.write(discount_row, len(sale_lines) + 1, '-', discount_percent_format)

        # Write DISCOUNT IN VALUE row (amounts)
        discount_value_row = discount_row + 1
        worksheet.write(discount_value_row, 0, 'DISCOUNT IN VALUE', discount_format)

        total_discount_amount = 0
        for col_idx, line in enumerate(sale_lines, 1):
            discount_amount = discount_amounts.get(line.id, 0)
            if discount_amount > 0:
                worksheet.write(discount_value_row, col_idx, discount_amount, discount_format)
                total_discount_amount += discount_amount
            else:
                worksheet.write(discount_value_row, col_idx, '-', discount_format)

        # Write total discount amount
        worksheet.write(discount_value_row, len(sale_lines) + 1, total_discount_amount, discount_format)

        # Write MARGIN row (percentages) - FIXED ROW POSITIONING
        margin_row = discount_value_row + 1
        worksheet.write(margin_row, 0, 'MARGIN', margin_percent_format)

        total_margin_percent = 0
        margin_count = 0
        for col_idx, line in enumerate(sale_lines, 1):
            margin_percent = margin_percentages.get(line.id, 0)
            if margin_percent > 0:
                worksheet.write(margin_row, col_idx, margin_percent / 100, margin_percent_format)
                total_margin_percent += margin_percent
                margin_count += 1
            else:
                worksheet.write(margin_row, col_idx, '-', margin_percent_format)

        # Write average margin percentage - FIXED CALCULATION
        if margin_count > 0:
            avg_margin = total_margin_percent / 100
            worksheet.write(margin_row, len(sale_lines) + 1, avg_margin, margin_percent_format)
        else:
            worksheet.write(margin_row, len(sale_lines) + 1, '-', margin_percent_format)

        # Write MARGIN IN VALUE row (amounts)
        margin_value_row = margin_row + 1
        worksheet.write(margin_value_row, 0, 'MARGIN IN VALUE', margin_format)

        total_margin_amount = 0
        for col_idx, line in enumerate(sale_lines, 1):
            margin_amount = margin_amounts.get(line.id, 0)
            if margin_amount > 0:
                worksheet.write(margin_value_row, col_idx, margin_amount, margin_format)
                total_margin_amount += margin_amount
            else:
                worksheet.write(margin_value_row, col_idx, '-', margin_format)

        # Write total margin amount
        worksheet.write(margin_value_row, len(sale_lines) + 1, total_margin_amount, margin_format)

        # Write NET AMOUNT row (TOTAL COST - DISCOUNT + MARGIN)
        net_row = margin_value_row + 1
        worksheet.write(net_row, 0, 'NET AMOUNT', total_format)

        total_net = 0
        for col_idx, line in enumerate(sale_lines, 1):
            # Get total cost for this column (same calculation as TOTAL COST row)
            categorized_total = 0
            for category in product_categories:
                category_id = category.id if category else 0
                categorized_total += data_matrix.get(category_id, {}).get(line.id, 0)

            # Add labor cost for this column
            labor_cost = labor_costs.get(line.id, 0)

            # Total cost = categorized costs + labor
            col_total_cost = categorized_total + labor_cost

            # Get margin and discount amounts
            discount_amount = discount_amounts.get(line.id, 0)
            margin_amount = margin_amounts.get(line.id, 0)

            # Calculate NET AMOUNT: Total Cost + Margin in Value - Discount in Value
            net_value = col_total_cost + margin_amount - discount_amount

            if net_value > 0:
                worksheet.write(net_row, col_idx, net_value, total_format)
                total_net += net_value
            else:
                worksheet.write(net_row, col_idx, '-', total_format)

        # Write total net amount
        worksheet.write(net_row, len(sale_lines) + 1, total_net, total_format)

        # Write project summary
        summary_row = net_row + 3
        summary_format = workbook.add_format({
            'align': 'left', 'valign': 'vcenter', 'border': 1, 'bold': True, 'bg_color': '#F5F5F5'
        })
        summary_value_format = workbook.add_format({
            'align': 'right', 'valign': 'vcenter', 'border': 1, 'bold': True,
            'num_format': '#,##0.00', 'bg_color': '#F5F5F5'
        })

        worksheet.write(summary_row, 0, 'PROJECT COST', summary_format)
        worksheet.write(summary_row, 1, grand_total, summary_value_format)
        worksheet.write(summary_row + 1, 0, 'PROJECT LABOR', summary_format)
        worksheet.write(summary_row + 1, 1, total_labor, summary_value_format)
        worksheet.write(summary_row + 2, 0, 'PROJECT DISCOUNT', summary_format)
        worksheet.write(summary_row + 2, 1, total_discount_amount, summary_value_format)
        worksheet.write(summary_row + 3, 0, 'PROJECT MARGIN', summary_format)
        worksheet.write(summary_row + 3, 1, total_margin_amount, summary_value_format)
        worksheet.write(summary_row + 4, 0, 'NET TOTAL', summary_format)
        worksheet.write(summary_row + 4, 1, total_net, summary_value_format)

        workbook.close()
        output.seek(0)

        filename = f"Costing_Sheet_{self.name.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        return {
            'file_data': base64.b64encode(output.read()),
            'filename': filename
        }

    def _get_costing_data_from_lines(self):
        """Extract costing data based on sale order lines and related tasks/BOM"""
        # Get all sale order lines (these will be our columns)
        sale_lines = self.order_line.filtered(lambda l: l.product_id)

        # Get all product categories from sale.bom lines (these will be our rows)
        product_categories = set()
        data_matrix = {}  # {category_id: {line_id: total_cost}}
        labor_costs = {}  # {line_id: total_labor_cost}
        margin_percentages = {}  # {line_id: average_margin_percentage}
        margin_amounts = {}  # {line_id: total_margin_amount}
        discount_percentages = {}  # {line_id: average_discount_percentage}
        discount_amounts = {}  # {line_id: total_discount_amount}

        # Process each sale order line
        for line in sale_lines:
            # Initialize data for this line
            labor_costs[line.id] = 0
            margin_percentages[line.id] = 0
            margin_amounts[line.id] = 0
            discount_percentages[line.id] = 0
            discount_amounts[line.id] = 0

            # Find tasks related to this sale order line
            tasks = self.env['project.task'].search([
                ('sale_order_line_id', '=', line.id)
            ])

            # Calculate data from tasks
            total_margin_percent = 0
            total_margin_amount = 0
            total_discount_percent = 0
            total_discount_amount = 0
            task_count = 0

            # Process each task
            for task in tasks:

                # Add labor cost from task's over_head_cost
                if hasattr(task, 'over_head_cost') and task.over_head_cost:
                    labor_costs[line.id] += task.over_head_cost

                # Add margin data
                if hasattr(task, 'margin') and task.margin:
                    total_margin_percent = task.margin
                    task_count = 1

                # FIXED: Use correct field name
                if hasattr(task, 'margin_amount') and task.margin_amount:
                    total_margin_amount += task.margin_amount

                # Add discount data
                if hasattr(task, 'discount') and task.discount:
                    total_discount_percent = task.discount

                if hasattr(task, 'discount_amount_on_quantity') and task.discount_amount_on_quantity:
                    total_discount_amount += task.discount_amount_on_quantity

                # Get sale.bom lines for this task
                bom_lines = task.sale_bom_ids

                # Process each BOM line
                for bom_line in bom_lines:
                    if bom_line.product_id and bom_line.product_id.categ_id:
                        category = bom_line.product_id.categ_id
                        product_categories.add(category)

                        # Initialize data structure
                        if category.id not in data_matrix:
                            data_matrix[category.id] = {}
                        if line.id not in data_matrix[category.id]:
                            data_matrix[category.id][line.id] = 0

                        # FIXED: Use correct field name
                        cost = bom_line.line_total * task.quantity if hasattr(bom_line,
                                                              'line_total') and bom_line.line_total else bom_line.cost
                        data_matrix[category.id][line.id] += cost
                    else:
                        # Handle products without category
                        if 0 not in data_matrix:
                            data_matrix[0] = {}
                        if line.id not in data_matrix[0]:
                            data_matrix[0][line.id] = 0

                        # FIXED: Use correct field name
                        cost = bom_line.line_total * task.quantity if hasattr(bom_line,
                                                              'line_total') and bom_line.line_total else bom_line.cost
                        data_matrix[0][line.id] += cost
                        product_categories.add(None)  # Add None for uncategorized

            # Calculate averages - FIXED LOGIC
            if task_count > 0:
                margin_percentages[line.id] = total_margin_percent
                discount_percentages[line.id] = total_discount_percent

            # Set total amounts
            margin_amounts[line.id] = total_margin_amount
            discount_amounts[line.id] = total_discount_amount

        # Convert set to sorted list
        product_categories = sorted(list(product_categories),
                                    key=lambda x: x.complete_name if x else 'ZZZ_Uncategorized')

        return {
            'sale_lines': sale_lines,
            'product_categories': product_categories,
            'data_matrix': data_matrix,
            'labor_costs': labor_costs,
            'margin_percentages': margin_percentages,
            'margin_amounts': margin_amounts,
            'discount_percentages': discount_percentages,
            'discount_amounts': discount_amounts
        }
