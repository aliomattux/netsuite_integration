from odoo import api, fields, models, SUPERUSER_ID, _, exceptions
import logging
import json
_logger = logging.getLogger(__name__)
from pprint import pprint as pp
#from unicodedata import normalize
#Note to developer
#This functionality works most efficiently when you send the appropriate data type for the variable you are sending
#If you are sending price, make sure you send a float of double for example
#The Magento API extension is designed to compare and only update if a value is different and typing is used

class NetsuiteIntegrator(models.TransientModel):
    _inherit = 'netsuite.integrator'

    def sync_netsuite_all_inactive(self, job):
        conn = self.connection(job.netsuite_instance)

        vals = {
                'search_id': job.search_id,
                'record_type': job.record_type,
        }

        try:
            _logger.info('Downloading all products from Netsuite for all inactive sync')
            response = conn.saved(vals)
            if not response.get('data'):
                return True

        except Exception as e:
            subject = 'Could not get all inactive data from Netsuite'
            self.env['integrator.logger'].submit_event('Netsuite', subject, str(e), False, 'admin')
            return True

        try:
            self.process_and_send_magento_all_inactives(response['data'])
        except Exception as e:
            subject = 'Could not update all inactive from Netsuite'
            self.env['integrator.logger'].submit_event('Netsuite', subject, str(e), False, 'admin')


    def process_and_send_magento_all_inactives(self, response_data):
        returned_data = []
        data = {}
        count = 0
        setup_obj = self.env['mage.setup']
        mage_obj = self.env['mage.integrator']
        instances = setup_obj.search([])
        instance = instances[0]
        params = '/attributeapi/setattributes'

        for record in response_data:
            count += 1
            record = record['columns']
            sku = record.get('custitem36')
            internalid = record['internalid']['internalid']

            status = '2'
            entity_id = sku

            vals = [{
                    'name': 'status',
                    'value': status
                   }
            ]

            data[entity_id] = vals

            if count > 300:
                token = mage_obj._get_mage_access_token(False, instance)
                _logger.info('Calling Magento to check/set inactive')
                try:
                    response = mage_obj._mage_rest_call(instance, token, params, data)
                    response = json.loads(response)
                    returned_data.append(response)
                except Exception as e:
                    _logger.critical(e)
                    raise exceptions.UserError(str(e))

                _logger.info('Products disabled successfully')
                data = {}
                count = 0

        if data:
            token = mage_obj._get_mage_access_token(False, instance)
            _logger.info('Calling Magento to check/set inactive')
            try:
                response = mage_obj._mage_rest_call(instance, token, params, data)
                response = json.loads(response)
                returned_data.append(response)
            except Exception as e:
                _logger.critical(e)
                raise exceptions.UserError(str(e))

            _logger.info('Products disabled successfully')

        return self.process_and_send_return_inactive_data(returned_data)


    def process_and_send_return_inactive_data(self, return_data):
        mapping_obj = self.env['generic.mapping']
        mappings = mapping_obj.search([])
        mapping_dict = {}
        for mapping in mappings:
            mapping_dict[mapping.mage_id] = {'netsuite_value': mapping['netsuite_name'], 'mage_value': mapping['mage_name']}

        csv_data = []

        import csv
        from datetime import datetime
        from time import sleep
        logging_obj = self.env['integrator.logger']
        filename = '/opt/odoo/csv/inactive_results.csv'
        with open(filename, 'w') as output_file:
            writer = False
            for set in return_data:
                if not set:
                    continue

                for sku, attributes in set.items():
#                    if type(sku) == unicode:
 #                       sku = normalize('NFKD', sku).encode('ascii', 'ignore')
                    row = {'sku': sku}
                    if not attributes:
                        continue

                    for attribute_name, attribute_values in attributes.items():
                        old_value = attribute_values['original_value']
                        new_value = attribute_values['new_value']
                        if mapping_dict.get(old_value):
                            old_value = mapping_dict[old_value]['netsuite_value']
                        if mapping_dict.get(new_value):
                            new_value = mapping_dict[new_value]['mage_value']
 #                       if type(old_value) == unicode:
  #                          old_value = normalize('NFKD', old_value).encode('ascii', 'ignore')
                        row[attribute_name + '_sent_value'] = old_value
#                        if type(new_value) == unicode:
 #                           new_value = normalize('NFKD', new_value).encode('ascii', 'ignore')
                        row[attribute_name + '_confirmed_value'] = new_value

                    if not writer:
                        fieldnames = list(row)
                        fieldnames.remove('sku')
                        fieldnames.sort()
                        fieldnames.insert(0, 'sku')
                        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
                        writer.writeheader()
                    writer.writerow(row)

            output_file.close()
            sleep(5)

        subject = 'Inactive Sync from Netsuite to Magento verification for %s' % datetime.now().strftime('%m-%d-%Y')
        html = 'See attached file for verification of products marked inactive'
        alert_type = 'attribute_sync_verification'
        logging_obj.send_notification(html, subject, True, alert_type, file_path=filename)

        return True
