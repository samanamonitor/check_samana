from .check import SAMMCheck

class SAMMDummyCheck(SAMMCheck):
    def run(self):
        self.start = time.time()
        self.done = True
        self.running = False
        self.stop = time.time()
        
