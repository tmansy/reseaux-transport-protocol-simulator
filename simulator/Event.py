# Generic event, a couple (context , callback)
#
# The callback method is called with context as argument
# upon event occurence (responsibility of simulator)
class Event:
    
    def __init__(self, ctx, callback):
        self.ctx = ctx
        self.callback = callback
        
    def run(self):
        self.callback(self.ctx)
    
    def __repr__(self):
        return f'Event({self.callback.__name__}, {self.ctx})'