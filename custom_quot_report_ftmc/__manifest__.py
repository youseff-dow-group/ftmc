{
    "name": "Custom Quotation Report Module",
    "summary": """Custom Quotation Report with additional fields""",
    "version": "0.1",
    "license": "LGPL-3",
    "author": "",
    "website": "",
    "depends": ['sale','crm','contacts','custom_sale_project'],
    "data": [
        'security/ir.model.access.csv',
        'views/sale_order_views.xml',
        'views/component_views.xml',
        'views/technical_description_views.xml',
        'report/report_template.xml',
        'report/template.xml',
    ],
}
