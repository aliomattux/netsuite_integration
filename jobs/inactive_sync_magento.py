from odoo import api, fields, models, SUPERUSER_ID, _, exceptions
import logging
_logger = logging.getLogger(__name__)

class NetsuiteIntegrator(models.TransientModel):
    _inherit = 'netsuite.integrator'

    def sync_netsuite_inactive_products(self, job):
        conn = self.connection(job.netsuite_instance)

        vals = {
                'search_id': job.search_id,
                'record_type': job.record_type,
        }

        try:
            _logger.info('Downloading all products from Netsuite for Magento inactive sync')
            response = conn.saved(vals)
        except Exception as e:
            subject = 'Could not get inactive data from Netsuite'
            self.env['integrator.logger'].submit_event('Netsuite', subject, str(e), False, 'admin')
            return True

        try:
            self.process_and_send_magento_inactive_products(response['data'])
        except Exception as e:
            subject = 'Could not push all Magento prices from Netsuite'
            self.env['integrator.logger'].submit_event('Netsuite', subject, str(e), False, 'admin')
            return True


    def process_and_send_magento_inactive_products(self, response_data):
        data = {}
        count = 0
        setup_obj = self.env['mage.setup']
        mage_obj = self.env['mage.integrator']
        instances = setup_obj.search([])
        instance = instances[0]
        params = '/attributeapi/setattributes'

        mage_skus = self.find_all_magento_netsuite_reference()

        for record in response_data:
            record = record['columns']
            sku = record.get('custitem36')
            internalid = record['internalid']['internalid']

            if not sku:
                _logger.info('Row from Netsuite contains no SKU')
                continue

            product = mage_skus.get(sku.lower())
            if not product:
                _logger.error('Product: %s has no Magento reference'%sku)
                continue

            entity_id = product['entity_id']
            if not entity_id:
#                _logger.error('Product: %s has no Magento reference to update price'%sku)
                continue

            self.env.cr.execute("DELETE FROM product WHERE entity_id = '%s'"%str(entity_id))
            self.env.cr.execute("DELETE FROM product WHERE internalid = '%s'"%str(internalid))

            vals = [{
                'name': 'status',
                'value': '2',
            }]

            count += 1
            data[str(entity_id)] = vals
            if count > 300:
                token = mage_obj._get_mage_access_token(False, instance)
#                _logger.info('Calling Magento to inactivate products')
                try:
                    response = mage_obj._mage_rest_call(instance, token, params, data)
                except Exception as e:
                    _logger.critical(e)
                    _logger.info(data)
                    raise exceptions.UserError(str(e))
 #               _logger.info('Products inactivated successfully')
                data = {}
                count = 0
        if data:
            token = mage_obj._get_mage_access_token(False, instance)
            _logger.info('Calling Magento to inactivate product')
            response = mage_obj._mage_rest_call(instance, token, params, data)
            _logger.info('Products inactivated successfully')

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
