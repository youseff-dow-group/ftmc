
{
    'name': 'Sale Order Project',
    'version': '1.0',
    'author': 'Ghaith',
    'depends': ['sale','project'],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order_view.xml',
        'views/project_task_view.xml',
        'views/account_move_view.xml',
    ],
    'installable': True,
    'application': False,
}

