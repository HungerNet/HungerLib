class Buffer:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.captured = []

    def enableBuffer(self): self.enabled = True

    def disableBuffer(self): self.enabled = False

    def toggleBuffer(self): self.enabled = not self.enabled

    def clearBuffer(self): self.captured = []

    def printBuffer(self):
        for msg in self.captured:
            print(msg)
    
    def flushBuffer(self):
        self.printBuffer()
        self.clearBuffer()