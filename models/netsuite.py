from odoo import api, fields, models, SUPERUSER_ID, _

class NetsuiteSetup(models.Model):
    _name = 'netsuite.setup'

    last_inventory_sync_date = fields.Datetime('Last Inventory Sync Time')
    name = fields.Char('Name', required=True)
    debug_mode = fields.Selection([('none', 'None'), ('error', 'Error'), ('debug', 'All')], 'Debug Mode')
    url = fields.Char('RESTlet URL', required=True)
    create_order_url = fields.Char('Create Order URL')
    mobile_url = fields.Char('Mobile URL')
    account_number = fields.Char('Account Number', required=True)
    import_inactive_products = fields.Boolean('Import Inactive Products')
    use_order_date = fields.Boolean('Use Order Date from Magento')
    client_key = fields.Char('Client Key', required=True)
    client_secret = fields.Char('Client Secret', required=True)
    token_key = fields.Char('Token Key', required=True)
    token_secret = fields.Char('Token Secret', required=True)
