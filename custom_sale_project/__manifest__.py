{
    'name': 'Sale Order Project',
    'version': '1.0',
    'author': 'Ghaith',
    'depends': ['sale', 'project'],
    'data': [
        'security/ir.model.access.csv',
        'security/groups.xml',
        'wizard/multiple_product_views.xml',
        'views/sale_order_view.xml',
        'views/project_task_view.xml',
        'views/product_product_view.xml',
        'views/account_move_view.xml',
        'views/mrp_bom_view.xml',
    ],
    'installable': True,
    'application': False,
}
