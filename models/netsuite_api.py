from odoo import api, fields, models, SUPERUSER_ID, _, exceptions
from SuiteREST2py import NLRequest

class NetsuiteIntegrator(models.TransientModel):
    _name = 'netsuite.integrator'

    def connection(self, instance, url_override=None):
        url = instance.url
        account_number = instance.account_number
        client_key = instance.client_key
        client_secret = instance.client_secret
        token_key = instance.token_key
        token_secret = instance.token_secret

        if url_override:
            url = url_override

        return NLRequest(url, account_number, client_key, client_secret, token_key, token_secret)


    def get_instance_id(self):
        setup_obj = self.env['netsuite.setup']
        setups = setup_obj.search([])
        if setups:
            return setups[0].id

        raise exceptions.UserError('No Netsuite connection is setup')


    def upsert_netsuite_fields(self, conn, data):
        try:
            data = {'records': data}
            response = conn.upsert(data)
#            if response.get('data') and response['data'].get('errors'):
 #               subject = 'Netsuite Upsert completed with Errors'
#                self.env['integrator.logger'].submit_event('Bronto', subject, str(response['data']['errors']), False, 'admin')
        except Exception as e:
            subject = 'Could not upsert record to Netsuite'
            self.env['integrator.logger'].submit_event('Netsuite', subject, str(e), False, 'admin')

        return True
