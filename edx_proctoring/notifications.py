import logging
import time

from celery import Celery
from kombu import Exchange

from django.conf import settings

log = logging.getLogger(__name__)


class ProctorNotificator(object):
    _celery_app = None
    _exchange = None

    _exchange_name = 'edx.proctoring.event'
    _routing_key = 'edx.proctoring.event'
    _subscribers = ['WEB_ASSISTANT']

    @classmethod
    def notify(cls, msg, provider_name=None):
        if provider_name and provider_name not in cls._subscribers:
            return

        msg['initiator'] = 'edx.proctoring'
        msg['created'] = time.time()

        log.info('Publish notification: %s' % str(msg))

        celery_app = cls._get_celery_app()
        with celery_app.producer_or_acquire() as producer:
            producer.publish(msg,
                             serializer='json',
                             exchange=cls._get_exchange(),
                             routing_key=cls._routing_key,
                             retry=True,
                             retry_policy={
                                 'interval_start': 0,  # First retry immediately,
                                 'interval_step': 2,  # then increase by 2s for every retry.
                                 'interval_max': 5,  # but don't exceed 5s between retries.
                                 'max_retries': 10
                             })

    @classmethod
    def _get_celery_app(cls):
        if cls._celery_app is None:
            broker = settings.BROKER_URL
            if broker:
                cls._celery_app = Celery('proctoring_notifications', broker=broker)
            else:
                raise Exception('BROKER_URL is not set!')
        return cls._celery_app

    @classmethod
    def _get_exchange(cls):
        if cls._exchange is None:
            cls._exchange = Exchange(cls._exchange_name, type='fanout', durable=True)
        return cls._exchange
