from odoo import api, fields, models, SUPERUSER_ID, _
import logging
_logger = logging.getLogger(__name__)

from pprint import pprint as pp

TYPE_MAP = {
    'Kit': 'kitpackage',
    'InvtPart': 'inventoryitem',
    'Assembly': 'assemblyitem',
    'NonInvtPart': 'noninventoryitem',
    'Group': 'group',
    'OthCharge': 'othercharge',
}

class NetsuiteIntegrator(models.TransientModel):
    _inherit = 'netsuite.integrator'

    def sync_all_netsuite_products(self, job):
        #Main for Netsuite
        #Item must be enabled and mage sync box checked
        #MFR Sku must not be null
        conn = self.connection(job.netsuite_instance)
        vals = {
                'search_id': job.search_id,
                'record_type': job.record_type,
        }

        try:
            _logger.info('Downloading all products from Netsuite')
            response = conn.saved(vals)
        except Exception as e:
            subject = 'Could not get all product data from Netsuite'
            self.env['integrator.logger'].submit_event('Netsuite', subject, str(e), False, 'admin')
            return False

        return self.process_item_response(response['data'])


    def sync_updated_netsuite_products(self, job):
        conn = self.connection(job.netsuite_instance)
        vals = {
                'search_id': job.search_id,
                'record_type': job.record_type,
        }

        try:
            _logger.info('Downloading updated products from Netsuite')
            response = conn.saved(vals)
        except Exception as e:
            subject = 'Could not get updated product data from Netsuite'
            self.env['integrator.logger'].submit_event('Netsuite', subject, str(e), False, 'admin')
            return True

        return self.process_item_response(response['data'])


    def find_netsuite_integrator_product(self, internalid=False, sku=False):
        product_obj = self.env['product']
        if internalid:
            products = product_obj.search([('internalid', '=', internalid)])
            if products:
                return products[0].id

        if sku:
            query = "SELECT id FROM product WHERE LOWER(sku) = LOWER('%s')"%sku
            self.env.cr.execute(query)
            res = self.env.cr.dictfetchall()
            if res:
                return res[0]['id']

        return False


    def process_item_response(self, response_data):
        product_obj = self.env['product']
        errors = 0
        message = ""
        for record in response_data:
            try:
                vals = self.netsuite_to_odoo_vals(record)
                products = product_obj.search([('internalid', '=', record['id'])])

                if products:
                    if len(products) > 1:
                        for product in products[1:]:
                            product.unlink()

                    product = products[0]
                    if product.sku != vals.get('sku'):
                        vals['entity_id'] = None

                    else:
                        if product.entity_id:
                            del vals['name']

                    product.write(vals)
#                    _logger.info('Update Product: %s'%vals['sku'])
                    self.env.cr.commit()

                else:
                    query = "SELECT id FROM product WHERE LOWER(sku) = LOWER('%s')"%vals['sku']
                    self.env.cr.execute(query)
                    res = self.env.cr.dictfetchall()
                    if not res:
                        product_obj.create(vals)
                    else:
                        product = product_obj.browse(res[0]['id'])
                        product.write(vals)

#                    _logger.info('Created Product: %s'%vals['sku'])
                    self.env.cr.commit()


            except Exception as e:
                subject = 'Could not get process product data from Netsuite'
                self.env['integrator.logger'].submit_event('Netsuite', subject, str(e), False, 'admin')
                return False

        if errors > 0:
            subject = 'Error(s) ocurred on individual Netsuite product sync'
            self.env['integrator.logger'].submit_event('Netsuite', subject, message, False, 'admin')
        _logger.info('Product Sync to Integrator from Netsuite Completed')
        return True


    def check_boolean(self, value):
        if not value:
            return False
        if value == 'T':
            return True
        return False


    def netsuite_to_odoo_vals(self, record):
        record = record['columns']
        length, width, height, cubic_inches, cubic_feet, weight = 0, 0, 0, 0, 0, 0

        vals = {
            'sku': record.get('custitem36'),
            'ddn': record.get('custitem99'),
            'mpn': record.get('mpn'),
            'netsuite_vendor_name': record.get('vendorname'),
            'name': record.get('purchasedescription'),
            'price': record.get('baseprice'),
            'upc': record.get('custitem_pacejet_upc_code'),
            'internalid': record['internalid']['internalid'],
            'sale_description': record.get('salesdescription'),
            'purchase_description': record.get('purchasedescription'),
            'length': length,
            'width': width,
            'height': height,
            'cubic_inches': cubic_inches,
            'cubic_feet': cubic_feet,
            'weight': weight,
            'product_line': None,
            'product_department': None,
            'product_sub_department': None,
            'material': None,
            'category': None,
            'sub_category': None,
            'restricted': False,
            'sell_unit': None,
            'bin_min': record.get('custitem146'),
            'bin_max': record.get('custitem147')
        }

        if record.get('custitem110'):
            category = record['custitem110']['name']
            vals['category'] = category

        if record.get('custitem104'):
            sub_category = record['custitem104']['name']
            vals['sub_category'] = sub_category

        if record.get('custitem_line'):
            product_line = record['custitem_line']['name']
            vals['product_line'] = product_line

        if record.get('custitem_department'):
            product_department = record['custitem_department']['name']
            vals['product_department'] = product_department

        if record.get('custitem94'):
            sell_unit = record['custitem94']['name']
            vals['sell_unit'] = sell_unit

        if record.get('custitem_sub_department'):
            product_sub_department = record['custitem_sub_department']['name']
            vals['product_sub_department'] = product_sub_department

        if record.get('custitem_material'):
            material = record['custitem_material']['name']
            vals['material'] = material

        if record.get('weight'):
            weight = float(record.get('weight'))
            filter_weight = None
            if weight < 3:
                filter_weight = 'xs'
            elif weight >= 3 and weight <= 10:
                filter_weight = 's'
            elif weight > 10 and weight <= 20:
                filter_weight = 'm'
            elif weight > 20:
                filter_weight = 'l'
            vals['weight'] = weight
            vals['filter_weight'] = filter_weight

        if record.get('custitem101'):
            length = float(record.get('custitem101'))
            filter_size = None
            if length < 9:
                filter_size = 'xs'
            elif length >= 9 and length <= 24:
                filter_size = 's'
            elif length > 24 and length <= 48:
                filter_size = 'm'
            elif length > 48:
                filter_size = 'l'

            vals['length'] = length
            vals['filter_size'] = filter_size

        spray_paint = False
        hazardous = False
        ormd = False
        lithium = False
        if record.get('custitem_spray_paint'):
            spray_paint = record.get('custitem_spray_paint')

        if record.get('custitem_hazardous_checmicals'):
            hazardous = record.get('custitem_hazardous_checmicals')

        if record.get('custitem_lithium_batteries'):
            lithium = record.get('custitem_lithium_batteries')

        if record.get('custitem_ormd'):
            ormd = record.get('custitem_ormd')

        if spray_paint or hazardous or ormd or lithium:
            vals['restricted'] = True

        if record.get('custitem102'):
            width = float(record.get('custitem102'))
            vals['width'] = width

        if record.get('custitem103'):
            height = float(record.get('custitem103'))
            vals['height'] = height

        cube = length * width * height
        vals['cubic_inches'] = cube

        if cube > 0:
            cube = round(cube, 2)
            cubic_feet = round(cube / 1728, 2)

        vals['cubic_feet'] = cubic_feet

        if record.get('custitem123'):
            feed = record['custitem123']
            vals['netsuite_magento_feed'] = feed['name']

        if record.get('type'):
            type_value = record['type']['internalid']
            vals['netsuite_type'] = TYPE_MAP[type_value]

        dim_obj = self.env['stock.fulfillment.dimension']
        dimensions = []

        dims = dim_obj.search([])
        for dim in dims:
            dim_matched = False
            for prod_dim in dim.product_dimensions:
                if prod_dim.operation == 'equals':
                    if vals.get(prod_dim.product_field.name) == prod_dim.product_field_value:
                        dim_matched = True
                    else:
                        dim_matched = False
                        break

                elif prod_dim.operation == 'contains':
                    if vals.get(prod_dim.product_field.name) and prod_dim.product_field_value in vals.get(prod_dim.product_field.name):
                        dim_matched = True
                    else:
                        dim_matched = False
                        break

                elif prod_dim.operation == 'greaterthan':
                    val = self.get_numeric_value(vals.get(prod_dim.product_field.name))
                    if val:
                        val = val['value']
                        if val > self.parse_float(prod_dim.product_field_value):
                            dim_matched = True
                            continue

                    dim_matched = False
                    break

                elif prod_dim.operation == 'greaterthan_equals':
                    val = self.get_numeric_value(vals.get(prod_dim.product_field.name))
                    if val:
                        val = val['value']
                        if val >= self.parse_float(prod_dim.product_field_value):
                            dim_matched = True
                            continue

                    dim_matched = False
                    break

                elif prod_dim.operation == 'lesserthan':
                    val = self.get_numeric_value(vals.get(prod_dim.product_field.name))
                    if val:
                        val = val['value']
                        if val < self.parse_float(prod_dim.product_field_value):
                            dim_matched = True
                            continue

                    dim_matched = False
                    break

                elif prod_dim.operation == 'lesserthan_equals':
                    val = self.get_numeric_value(vals.get(prod_dim.product_field.name))
                    if val:
                        val = val['value']
                        if val <= self.parse_float(prod_dim.product_field_value):
                            dim_matched = True
                            continue

                    dim_matched = False
                    break


            if dim_matched:
                dimensions.append(dim.id)

        vals['dimensions'] = [(6, 0, dimensions)]
        return vals


    def get_numeric_value(self, value):
        try:
            val = float(value)
            return {'value': val}

        except Exception as e:
            return None


    def parse_float(self, value):
        try:
             return float(value)

        except Exception as e:
            return 0
