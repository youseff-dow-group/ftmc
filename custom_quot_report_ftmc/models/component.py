from odoo import models, fields, api


class ComponentMake(models.Model):
    _name = 'component.make'
    _description = 'Component Make/Manufacturer'

    name = fields.Char(string='Name', required=True)
    description = fields.Char(string='Description')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'Component Make name must be unique!')
    ]
