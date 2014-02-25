from app import app

from sms import SMSProvider

@app.task
def send_sms(receiver, content):
    '''
    Sends an sms with a given content to the receiver
    '''
    provider = SMSProvider.get_instance()
    provider.send_sms(receiver, content)
