from odoo import api, fields, models, SUPERUSER_ID, _

class NetsuiteJob(models.Model):
    _name = 'netsuite.job'
    name = fields.Char('Name', required=True)
    core_job = fields.Boolean('Core Job')
    url = fields.Char('URL')
    second_search_id = fields.Char('Second Search ID')
    search_id = fields.Char('Search ID')
    record_type = fields.Char('Record Type')
    netsuite_instance = fields.Many2one('netsuite.setup', 'Netsuite Instance', required=True)
    scheduler = fields.Many2one('ir.cron', 'Scheduler', readonly=True)
    mapping = fields.Many2one('netsuite.mapping', 'Mapping')
    python_model = fields.Many2one('ir.model', 'Python Model')
    python_function_name = fields.Char('Python Function Name', required=True)


    def button_execute_job(self):
        job = self
        result = self.import_resources(job)

        return True


    def import_resources(self, job):
        """
        """
        job_obj = self.env[job.python_model.name]
        return getattr(job_obj, job.python_function_name)(job)


    def button_schedule_netsuite_job(self):
        job = self
        if job.scheduler:
            return

        cron_id = self.create_netsuite_schedule(job.id, job.name)
        job.write({'scheduler': cron_id})
        return True


    def create_netsuite_schedule(self, job_id, job_name):
        vals = {'name': job_name,
                'active': False,
                'user_id': SUPERUSER_ID,
                'interval_number': 15,
                'interval_type': 'minutes',
                'numbercall': -1,
                'doall': False,
                'model': 'netsuite.job',
                'function': 'button_execute_job',
                'args': '([' + str(job_id) +'],)',
        }

        return self.env['ir.cron'].create(vals)
