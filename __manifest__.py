{
    'name': 'Integrator - Netsuite',
    'version': '1.1',
    'author': 'Kyle Waid',
    'category': 'Sales Management',
    'depends': ['integrator', 'integrator_product', 'integrator_sale'],
    'website': 'https://www.gcotech.com',
    'description': """
    """,
    'data': [
             'security/ir.model.access.csv',
             'views/core.xml',
             'views/generic_mapping.xml',
             'views/jobs.xml',
    ],
    'test': [
    ],
    'installable': True,
    'auto_install': False,
}
