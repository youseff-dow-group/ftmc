from odoo import models, fields, api


class TechnicalDescription(models.Model):
    _name = 'technical.description'

    name = fields.Char(string='Name', required=True)

    _sql_constraints = [
        ('name_uniq', 'unique (name)', ' Name must be unique!')
    ]
