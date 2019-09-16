class SubprocessException(Exception):

    def __init__(self, index: int, exception: Exception):
        super().__init__("Exception {} raised in subprocess, task index {}".format(type(exception), index))
        self.index = index
        self.raised = exception