from odoo import api, fields, models, SUPERUSER_ID, _, exceptions
from pprint import pprint as pp
import logging
import json
_logger = logging.getLogger(__name__)
#from unicodedata import normalize
#Note to developer
#This functionality works most efficiently when you send the appropriate data type for the variable you are sending
#If you are sending price, make sure you send a float of double for example
#The Magento API extension is designed to compare and only update if a value is different and typing is used

class NetsuiteIntegrator(models.TransientModel):
    _inherit = 'netsuite.integrator'

    def sync_netsuite_attributes(self, job):
        return self.sync_netsuite_attributes_processor(job, True)


    def sync_netsuite_updated_attributes(self, job):
        return self.sync_netsuite_attributes_processor(job, False)


    def sync_netsuite_attributes_processor(self, job, sync_all):
        conn = self.connection(job.netsuite_instance)

        vals = {
                'search_id': job.search_id,
                'record_type': job.record_type,
        }

        try:
            _logger.info('Downloading all products from Netsuite for Magento attribute sync')
            response = conn.saved(vals)
            if not response.get('data'):
                return True

        except Exception as e:
            subject = 'Could not get attribute data from Netsuite'
            self.env['integrator.logger'].submit_event('Netsuite', subject, str(e), False, 'admin')
            return True

        special_price_vals = {}

        if job.second_search_id:
            vals = {
                'search_id': job.second_search_id,
                'record_type': job.record_type,
            }

            try:
                _logger.info('Downloading all special prices from Netsuite for Magento attribute sync')
                second_response = conn.saved(vals)
                special_price_vals = self.extract_second_search_vals(second_response['data'])
            except Exception as e:
                subject = 'Could not get or process special price data from Netsuite'
                self.env['integrator.logger'].submit_event('Netsuite', subject, str(e), False, 'admin')
        if True:
#        try:
            self.process_and_send_magento_attributes(response['data'], special_price_vals, sync_all)
 #       except Exception as e:
  #          subject = 'Could not push all Magento prices from Netsuite'
   #         self.env['integrator.logger'].submit_event('Netsuite', subject, str(e), False, 'admin')


    def extract_second_search_vals(self, records):
        res = {}
        for record in records:
            record = record['columns']
            res[record['internalid']['internalid']] = record['unitprice']
        return res


    def get_field_mapping(self, field_name):
        mapping_obj = self.env['generic.mapping']
        mappings = mapping_obj.search([('name', '=', field_name)])
        map = {}
        for mapping in mappings:
            map[mapping.netsuite_id] = mapping.mage_id

        return map


    def get_related_record_name(self, value_dict, field_name):
        if value_dict.get(field_name):
            return value_dict[field_name]['name']
        else:
            return ''


    def process_and_send_magento_attributes(self, response_data, special_price_data, sync_all):
        returned_data = []
        data = {}
        count = 0
        setup_obj = self.env['mage.setup']
        mage_obj = self.env['mage.integrator']
        instances = setup_obj.search([])
        instance = instances[0]
        params = '/attributeapi/setattributes'

        availability_status_map = self.get_field_mapping('availability_status')
        free_ship_map = self.get_field_mapping('free_shipping')

        mage_skus = self.find_all_magento_netsuite_reference()

        for record in response_data:
            """{'columns': {'baseprice': 0.5,
                     'custitem101': 1,
                     'custitem104': {'internalid': '31', 'name': 'Cable Rail'},
                     'custitem106': {'internalid': '1', 'name': 'Free'},
                     'custitem107': {'internalid': '22',
                                     'name': 'Guaranteed 3 Day Delivery'},
                     'custitem110': {'internalid': '15', 'name': 'Railing Cable'},
                     'custitem36': '3375',
                     'custitem_color_family': {'internalid': '11', 'name': 'White'},
                     'custitem_google_feed': True,
                     'custitem_google_price': 0,
                     'custitem_hazardous_checmicals': False,
                     'custitem_lithium_batteries': False,
                     'custitem_magento_disabled': False,
                     'custitem_not_returnable': False,
                     'custitem_ormd': False,
                     'custitem_spray_paint': False,
                     'custitemcustitem_dd_ltlreq': False,
                     'internalid': {'internalid': '14587', 'name': '14587'},
                     'weight': 0.1},
             'id': '14587',
             'recordtype': 'inventoryitem'}"""

            record = record['columns']
            sku = record.get('custitem36')
            internalid = record['internalid']['internalid']
            if not sku:
                _logger.info('Price row from Netsuite contains no SKU')
                continue

            netsuite_product_category = self.get_related_record_name(record, 'custitem110')
            netsuite_product_subcategory = self.get_related_record_name(record, 'custitem104')
            netsuite_not_returnable = record.get('custitem_not_returnable')

            #Shipping time availability
            availability_field = record.get('custitem107')
            if availability_field:
                availability_field = availability_field['internalid']

            free_shipping_field = record.get('custitem106')
            if free_shipping_field:
                free_shipping_field = free_shipping_field['internalid']

            availability_status = availability_status_map.get(availability_field)
            free_shipping = free_ship_map.get(free_shipping_field)

            ormd = record.get('custitem_ormd')
            hazardous = record.get('custitem_hazardous_checmicals')
            spray_paint = record.get('custitem_spray_paint')
            lithium_batteries = record.get('custitem_lithium_batteries')
            ground_shipping_only = '2'
            if record.get('custitem_ground_shipping_only'):
                ground_shipping_only = '1'

            color_family = record.get('custitem_color_family')
            if color_family:
                color_family = color_family['name']

            length = record.get('custitem101') or 0
            weight = record.get('weight') or 0
            #Magento only uses 4 decimal places and also forces it
            weight = round(weight, 4)
            #Weight seems to be a string in Magento
            weight = str(weight)
            ltl_required = record.get('custitemcustitem_dd_ltlreq')

            status = '1'
            magento_disabled = record.get('custitem_magento_disabled')
            if magento_disabled:
                status = '2'

            google_shipping_price = record.get('custitem_google_price', 0)
            google_shipping_price = float(google_shipping_price)

            google_feed_category = record.get('custrecord_google_category')

            google_feed = '0'
            magento_google_feed = record.get('custitem_google_feed')
            if magento_google_feed:
                google_feed = '1'

            if not weight:
                weight = 0

     #       product = mage_skus.get(sku.lower())
            entity_id = sku
    #        if not product:
 #               _logger.error('Product: %s has no Magento reference to update price'%sku)
   #             continue

#            entity_id = product['entity_id']
 #           if not entity_id:
#                _logger.error('Product: %s has no Magento reference to update price'%sku)
  #              continue

            vals = [
                   {
                    'name': 'ground_shipping_only',
                    'value': ground_shipping_only
                   },
                   {
                    'name': 'google_shipping_price',
                    'value': google_shipping_price
                   },
                   {
                    'name': 'is_imported',
                    'value': google_feed
                   },
                   {
                    'name': 'google_feed_category',
                    'value': google_feed_category
                   },
                   {
                    'name': 'color_family',
                    'value': color_family
                   },
                   {
                    'name': 'status',
                    'value': status
                   },
                   {
                    'name': 'freight_item',
                    'value': ltl_required
                   },
                   {
                    'name': 'availability_status',
                    'value': availability_status
                   },
                   {
                    'name': 'free_shipping',
                    'value': free_shipping
                   },
                   {
                    'name': 'orm_d',
                    'value': ormd
                   },
                   {
                    'name': 'contains_lithium_ion_batteries',
                    'value': lithium_batteries
                   },
                   {
                    'name': 'hazardous_chemicals',
                    'value': hazardous
                   },
                   {
                    'name': 'spray_paint',
                    'value': spray_paint
                   },
                   {
                    'name': 'shipping_calc_length',
                    'value': float(length)
                   },
                   {
                    'name': 'weight',
                    'value': weight
                   },
                   {
                    'name': 'netsuite_product_category',
                    'value': netsuite_product_category
                   },
                   {
                    'name': 'netsuite_product_subcategory',
                    'value': netsuite_product_subcategory
                   },
                   {
                    'name': 'netsuite_not_returnable',
                    'value': netsuite_not_returnable
                   }
            ]

            price = record.get('baseprice')

            if price or sku == 'Snubber':
                vals.extend([{
                     'name': 'price',
                     'value': float(price),
                }])

            if record.get('internalid') and special_price_data.get(internalid) and special_price_data.get(internalid) != 0:
                vals.extend([{
                    'name': 'special_price',
                    'value': float(special_price_data.get(internalid))
                },
                {
                    'name': 'special_from_date',
                    'value': '2020-11-01 00:00:00',
                },
                {
                    'name': 'special_to_date',
                    'value': None,
                }])

            else:
                vals.extend([{
                    'name': 'special_price',
                    'value': None
                },
                {
                   'name': 'special_from_date',
                    'value': '2020-11-01 00:00:00',
                },
                {
                    'name': 'special_to_date',
                    'value': '2020-11-01 00:00:00',
                }])

            count += 1
            data[entity_id] = vals

            if count > 300:
                token = mage_obj._get_mage_access_token(False, instance)
                _logger.info('Calling Magento to update Attributes')
                try:
                    response = mage_obj._mage_rest_call(instance, token, params, data)
                    response = json.loads(response)
                    returned_data.append(response)
                except Exception as e:
                    _logger.critical(e)
                    raise exceptions.UserError(str(e))
                _logger.info('Attributes Updated successfully')
                data = {}
                count = 0

        if data:
            token = mage_obj._get_mage_access_token(False, instance)
            _logger.info('Calling Magento to update Attributes')
            response = mage_obj._mage_rest_call(instance, token, params, data)
            response = json.loads(response)
            returned_data.append(response)
            _logger.info('Attributes Updated successfully')

        return self.process_and_send_return_data(returned_data, sync_all)


    def get_attribute_map(self):
        return True


    def process_and_send_return_data(self, return_data, sync_all):
        mapping_obj = self.env['generic.mapping']
        mappings = mapping_obj.search([])
        mapping_dict = {}
        for mapping in mappings:
            mapping_dict[mapping.mage_id] = {'netsuite_value': mapping['netsuite_name'], 'mage_value': mapping['mage_name']}

        attribute_map = self.get_attribute_map()
        csv_data = []

        import csv
        from datetime import datetime
        from time import sleep

        logging_obj = self.env['integrator.logger']
        filename = '/opt/odoo/csv/attribute_results.csv'
        with open(filename, 'w') as output_file:
            writer = False
            for set in return_data:
                for sku, attributes in set.items():
                  #  if type(sku) == unicode:
                   #     sku = normalize('NFKD', sku).encode('ascii', 'ignore')
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
 #                       if type(new_value) == unicode:
  #                          new_value = normalize('NFKD', new_value).encode('ascii', 'ignore')
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

        if sync_all:
            subject = 'Attribute Sync from Netsuite to Magento verification for %s' % datetime.now().strftime('%m-%d-%Y')
            html = 'See attached file for verification of values'
            alert_type = 'attribute_sync_verification'
            logging_obj.send_notification(html, subject, True, alert_type, file_path=filename)

        return True


    def find_all_magento_netsuite_reference(self):
        #There is a data integrity problem at DD. May be caused by activating/inactivating
        #Re-using items, changing skus, etc. This attemps to find the best match
        data = {}

        query = "SELECT LOWER(sku) AS sku, MAX(internalid) AS internalid, MAX(entity_id) AS entity_id" \
            "\nFROM product" \
            "\nGROUP BY sku"
        cr.execute(query)
        res = cr.dictfetchall()
        if not res:
            return False

        #Should only be one result
        for result in res:
            data[result['sku']] = {'entity_id': result['entity_id']}

        return data



