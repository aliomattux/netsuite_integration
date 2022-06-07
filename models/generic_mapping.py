from odoo import api, fields, models, SUPERUSER_ID, _

class GenericMapping(models.Model):
    _name = 'generic.mapping'
    netsuite_name = fields.Char('Netsuite Name')
    mage_name = fields.Char('Mage Name')
    netsuite_id = fields.Char('Netsuite ID')
    mage_id = fields.Char('Mage ID')
    name = fields.Char('Name')
