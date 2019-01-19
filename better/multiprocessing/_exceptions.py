class SubprocessException(Exception):

    def __init__(self, index: int, raised: Exception):
        super().__init__("Exception '{}' raised in subprocess, task index {}".format(raised, index))
        self.index = index
        self.raised = raised