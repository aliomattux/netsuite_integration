from odoo import api, fields, models, SUPERUSER_ID, _
import logging
_logger = logging.getLogger(__name__)

TYPE_MAP = {
    'Kit': 'kitpackage',
    'InvtPart': 'inventoryitem',
    'Assembly': 'assemblyitem',
    'NonInvtPart': 'noninventoryitem',
    'Group': 'group',
}

class NetsuiteIntegrator(models.TransientModel):
    _inherit = 'netsuite.integrator'


    def sync_netsuite_inventory(self, job):
        conn = self.connection(job.netsuite_instance)
        logger_obj = self.env['integrator.logger']

        vals = {
                'search_id': job.search_id,
                'record_type': job.record_type,
        }

        try:
            _logger.info('Downloading all products from Netsuite')
            response = conn.saved(vals)
        except Exception as e:
            subject = 'Could not download stock data from Netsuite'
            self.env['integrator.logger'].submit_event('Netsuite', subject, str(e), False, 'admin')
            return True

        self.process_and_send_magento_custom_inventory(response['data'])


    def convert_magento_boolean(self, value):
        if value:
            return '1'
        else:
            return '0'


    def process_and_send_magento_custom_inventory(self, response_data):
        data = {}
        count = 0
        setup_obj = self.env['mage.setup']
        mage_obj = self.env['mage.integrator']
        instances = setup_obj.search([])
        instance = instances[0]
        params = '/stockapi/setstock/test'

        mage_skus = self.find_all_magento_netsuite_reference()

        backorders_map = {
            'No Backorders': '0',
            'Allow Qty Below 0': '1',
            'Allow Qty Below 0 and Notify': '2'
        }

        for record in response_data:
            record = record['columns']
            sku = record.get('custitem36')
            if not sku:
                continue

            product = mage_skus.get(sku.lower())
            if not product:
                _logger.info('Skipping Product due to no match')
                continue

            entity_id = product['entity_id']
            if not entity_id:
                continue

            qty = record.get('locationquantityavailable')
            if not qty:
                qty = 0

            manage_stock = self.convert_magento_boolean(record.get('custrecord_manage_stock'))
            backorders = record.get('custrecord_backorders')
            if backorders and backorders_map.get(backorders['name']):
                backorders = backorders_map[backorders['name']]
            else:
                #Allow backorder
                backorders = 1

            use_config_backorders = self.convert_magento_boolean(record.get('custrecord_use_config_backorders'))
            use_config_manage_stock = self.convert_magento_boolean(record.get('custrecord_use_config_manage_stock'))
            change_status_when_zero = self.convert_magento_boolean(record.get('custrecord_change_status_when_zero'))
            stock_status = '1'
            if change_status_when_zero == '1' and qty < 1:
                stock_status = '0'

            vals = {
                'use_config_backorders': use_config_backorders,
                'backorders': backorders,
                'manage_stock': manage_stock,
                'use_config_manage_stock': use_config_manage_stock,
                'is_in_stock': stock_status,
                'qty': qty,
            }

            count += 1
            data[str(entity_id)] = vals

            if count > 300:
                self.send_inventory_set(instance, params, data)
                data = {}
                count = 0

        if data:
            self.send_inventory_set(instance, params, data)

        return True


    def send_inventory_set(self, instance, params, data):
        mage_obj = self.env['mage.integrator']
        try:
            _logger.info('Sending bulk inventory data to Magento')
            token = mage_obj._get_mage_access_token(False, instance)
            response = mage_obj._mage_rest_call(instance, token, params, data)
            _logger.info('Inventory batch updated successfully')
        except Exception as e:
            subject = 'Error sending inventory set to Magento'
            self.env['integrator.logger'].submit_event('Magento 2x', subject, str(e), False, 'admin')
        finally:
            return True


    def find_all_magento_netsuite_reference(self):
        #There is a data integrity problem at DD. May be caused by activating/inactivating
        #Re-using items, changing skus, etc. This attemps to find the best match
        data = {}

        query = "SELECT LOWER(sku) AS sku, MAX(internalid) AS internalid, MAX(entity_id) AS entity_id" \
            "\nFROM product" \
            "\nGROUP BY sku"
        self.env.cr.execute(query)
        res = self.env.cr.dictfetchall()
        if not res:
            return False

        #Should only be one result
        for result in res:
            data[result['sku']] = {'entity_id': result['entity_id']}

        return data
