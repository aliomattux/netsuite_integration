from odoo import api, fields, models, SUPERUSER_ID, _
import logging
_logger = logging.getLogger(__name__)

from pprint import pprint as pp

class NetsuiteIntegrator(models.TransientModel):
    _inherit = 'netsuite.integrator'

    def sync_all_netsuite_shipping_method(self, job):
        conn = self.connection(job.netsuite_instance)
        vals = {
                'search_id': job.search_id,
                'record_type': job.record_type,
        }
        try:
            _logger.info('Downloading all shipping methods from Netsuite')
            response = conn.saved(vals)
        except Exception as e:
            subject = 'Could not get shipping method data from Netsuite'
            self.env['integrator.logger'].submit_event('Netsuite', subject, str(e), False, 'admin')
            return False

        return self.process_shipping_method_response(response['data'])


    def process_shipping_method_response(self, response_data):
        #{'internalid': {'internalid': '29596', 'name': '29596'},
        #'itemid': 'Local Delivery w/forklift'}
        shipping_obj = self.env['shipping.method']
        for record in response_data:
            record = record['columns']
            internalid = record['internalid']['internalid']
            name = record['itemid']

            shipping_methods = shipping_obj.search([('internalid', '=', internalid)])
            if not shipping_methods:
                shipping_method = shipping_obj.create({'internalid': internalid, 'name': name})
            else:
                shipping_method = shipping_methods[0]
                shipping_method.name = name
