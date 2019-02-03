import threading
import multiprocessing as mp
import logging

class LogPipeThread(threading.Thread):
    """ A thread to handle the dequeuing of log records from subprocesses to be handled by handlers of the main process

    Params:
        pipe (multiprocessing.Pipe): The communication medium of the records, this thread only receives
        loggers (dict): A diction of logger name to logger objects that shall have handlers associated with them
    """

    def __init__(self, pipe: mp.Pipe, loggers):
        threading.Thread.__init__(self)

        self.working = True
        self.receiveConnection = pipe[0]
        self.loggers = loggers

    def run(self):

        while self.working:
            while self.receiveConnection.poll():

                # Collect new log from sub-processes
                record = self.receiveConnection.recv()

                # Break up the record hierarchy - iterate through the hierarchy until a logger is found
                hierarchy = record.name.split(".")
                while hierarchy:
                    name = ".".join(hierarchy)
                    if name in self.loggers:
                        self.loggers[name].handle(record)
                        break
                    hierarchy.pop()

    def close(self):
        """ Update the threads working flag, this shall inform the thread to stop when it has finished any current work
        """
        self.working = False

class LogPipeHandler(logging.Handler):
    """ A handler for the subprocesses loggers that handles communicating the log information to the main process

    Params:
        pipe (multiprocessing.Pipe): The pipe which the records shall be communicated through
    """

    def __init__(self, pipe: mp.Pipe):
        logging.Handler.__init__(self, level=logging.DEBUG)
        self.sendConnection = pipe[1]

    def emit(self, record):
        self.sendConnection.send(record)