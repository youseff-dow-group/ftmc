from odoo import models, fields, api

from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move.line'

    discount_amount=fields.Float(string='Discount Amount')
