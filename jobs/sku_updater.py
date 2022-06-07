from odoo import api, fields, models, SUPERUSER_ID, _
import logging
_logger = logging.getLogger(__name__)

class NetsuiteIntegrator(models.TransientModel):
    _inherit = 'netsuite.integrator'

    def sync_netsuite_sku_changes(self, job):
        conn = self.connection(job.netsuite_instance)
        logger_obj = self.env['integrator.logger']

        vals = {
                'search_id': job.search_id,
                'record_type': job.record_type,
        }

        try:
            _logger.info('Downloading Sku Changes from Netsuite')
            response = conn.saved(vals)
        except Exception as e:
            subject = 'Could not get sku data from Netsuite'
            self.env['integrator.logger'].submit_event('Netsuite', subject, str(e), False, 'admin')
            return True

        self.process_and_send_magento_sku_changes(response['data'])


    def process_and_send_magento_sku_changes(self, response_data):
        data = {}
        setup_obj = self.env['mage.setup']
        mage_obj = self.env['mage.integrator']
        instances = setup_obj.search([])
        instance = instances[0]
        params = '/attributeapi/setattributes'

        #Get a dict of all skus
        mage_skus = self.find_all_magento_netsuite_reference()

        for record in response_data:
            record = record['columns']
            old_sku = record.get('custitem_old_sku')
            new_sku = record.get('custitem36')
            price = record.get('baseprice')

            if not price:
                price = 0

            if not new_sku:
                _logger.info('Sku has been deleted. Skipping')
                continue

            #If the new sku is in the dict, it has already been updated
            #Second check ensures if the sku changed was already imported as a new product and both records exist
            if mage_skus.get(new_sku.lower()) and mage_skus[new_sku.lower()]['entity_id']:
                _logger.info('Sku: %s has already been changed'%new_sku)
                continue

            product = mage_skus.get(old_sku.lower())
            #If the sku is updated but not a Magento product
            if not product or not product.get('entity_id'):
                query = "UPDATE product SET sku = '%s' WHERE LOWER(sku) = '%s'" % (new_sku, old_sku.lower())
                self.env.cr.execute(query)
                _logger.error('Sku: %s Not found in Magento Data'%old_sku)
                continue

            entity_id = product['entity_id']

            vals = [{
                'name': 'sku',
                'value': new_sku,
                'price': price,
            }]

            data[str(entity_id)] = vals

            try:
                token = mage_obj._get_mage_access_token(False, instance)
                _logger.info('Requesting Change in Magento for Datas')
                _logger.info(data)
                response = mage_obj._mage_rest_call(instance, token, params, data)
                _logger.info('Magento Sku update response')
                _logger.info(response)
                #Once the SKU is updated
                query = "UPDATE product SET sku = '%s' WHERE LOWER(sku) = '%s'" % (new_sku, old_sku.lower())
                self.env.cr.execute(query)
                self.env.cr.commit()
                data = {}
            except Exception as e:
                subject = 'Could not change Sku in Magento. Old Sku: %s, New Sku: %s' % (old_sku, new_sku)
                self.env['integrator.logger'].submit_event('Magento 2x', subject, str(e), False, 'admin')

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
