class Buffer:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.captured = []

    def enable(self): self.enabled = True

    def disable(self): self.enabled = False

    def toggle(self): self.enabled = not self.enabled

    def clear(self): self.captured = []

    def print(self):
        for msg in self.captured:
            print(msg)
    
    def flush(self):
        self.print()
        self.clear()