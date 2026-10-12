import json
from helpers.api import ApiHandler
from usr.plugins.requesty.helpers import scope
from usr.plugins.requesty.helpers.account import confirmation
from usr.plugins.requesty.helpers.configuration import atomic_write

class Account(ApiHandler):
    async def process(self,input,request):
        try:
            owner=scope.from_input(input)
            with self.thread_lock:
                if input.get('action','get')=='set':
                    atomic_write(scope.path(owner,'account.json'),json.dumps(confirmation(input.get('settings'))))
                elif input.get('action','get')!='get':raise ValueError('Unknown account action.')
                return {'ok':True,'account':scope.read(owner,'account.json',{}),'technically_verified':False}
        except ValueError as error:return {'ok':False,'error':str(error)}
