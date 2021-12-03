from utils.redisconn import REDIS
from rq.worker import Worker
from rq import Queue, Connection
from typing import Union

def run_worker(queues: Union[list, None]):
    queues = queues if queues else ['single', 'dual', 'chat']

    with Connection(REDIS):
        worker = Worker(map(Queue, queues))
        worker.work()