import time
import sys
import win32pipe, win32file, pywintypes
from collections import deque

class InputHandler():

    class Sample():
        def __init__(self, timestamp, foot_avg, head):
            self.timestamp = timestamp
            self.foot_avg = foot_avg
            self.head = head

        def __radd__(self, other):
            return other + self.avg
    
    def __init__(self):
        self.samples = deque([])
        #self.window = 200 # ms
        self.window = 95 # ms

        self.ducking = False

    def evict_old(self):
        now = round(time.time() * 1000.0)
        while len(self.samples) > 0 and self.samples[0].timestamp < now - self.window:
            self.samples.popleft()

    def is_jumping(self):
        ys = [s.foot_avg for s in self.samples]
        deltas = [ys[i+1] - ys[i] for i in range(max(0,len(ys)-1))]
        
        if len(deltas) >= 2:
            for delta in deltas:
                if delta < 0.035: #TODO: TUNE THIS
                    return False
            return True
        return False
    
        
        ys = [s.foot_avg for s in self.samples]
        dist = max(ys, default=0) - min(ys, default=0)
        return dist > 0.15

    def is_ducking(self):
        return self.ducking

    def update_duck(self):
        if self.is_jumping():
            self.ducking = False
        
        foot_ys = [s.foot_avg for s in self.samples]
        head_ys = [s.head for s in self.samples]
        foot_deltas = [foot_ys[i+1] - foot_ys[i] for i in range(max(0,len(foot_ys)-1))]
        head_deltas = [head_ys[i+1] - head_ys[i] for i in range(max(0,len(head_ys)-1))]

        def is_falling(deltas, sensitivity):
            for delta in deltas:
                if delta > -sensitivity:
                    return False
            return True

        def is_rising(deltas):
            for delta in deltas:
                if delta < 0.04:
                    return False
            return True
        
        if len(foot_deltas) >= 2:
            if not is_falling(foot_deltas, 0.05) and is_falling(head_deltas, 0.04):
                self.ducking = True
            elif is_rising(head_deltas):
                self.ducking = False
        return




        
        if self.is_jumping():
            self.ducking = False

        ys = [s.head for s in self.samples]
        top = max(ys, default=0)
        bot = min(ys, default=0)
        dist = top - bot
        if dist > 0.27:
            if ys.index(top) > ys.index(bot):
                self.ducking = False
            else:
                self.ducking = True
        
    def add_sample(self, time, l_foot_y, r_foot_y, head_y):
        foot_avg = (l_foot_y + r_foot_y) / 2.0
        self.samples.append(self.Sample(time, foot_avg, head_y))
        self.evict_old()

        self.update_duck()

    def between(self):
        dts = []
        for i in range(len(self.samples) - 1):
            dt = self.samples[i+1].timestamp - self.samples[i].timestamp
            dts.append(dt)
        return sum(dts)/max(len(dts), 1)
            

class InputHandlerPipe():

    class InputHandlerStamped(InputHandler):
        def __init__(self):
            super().__init__()
            self.created = round(time.time() * 1000.0)

    def try_set_pipe(self):
        print("trying to set pipe")
        try:
            self.pipe = win32file.CreateFile(
                r'\\.\pipe\joint_states',
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None
            )
            res = win32pipe.SetNamedPipeHandleState(self.pipe, win32pipe.PIPE_READMODE_MESSAGE, None, None)
            if res == 0:
                print(f"SetNamedPipeHandleState return code: {res}")
        except pywintypes.error as e:
            self.pipe = None
            if e.args[0] == 2:
                print("no pipe")
            elif e.args[0] == 109:
                print("broken pipe, bye bye")
            else:
                print(e)
            return False
        return True

    def update_state(self):
        if self.pipe is None:
            if not self.try_set_pipe():
                return

        # Only proceeds if we have a pipe
        while win32pipe.PeekNamedPipe(self.pipe, 0)[1] > 0:
            resp = win32file.ReadFile(self.pipe, 64*1024)
            (hr, resp) = resp
            resp = resp.decode("utf-16")
            data = resp.split(",")
            data = list(map(float, data))
            try:
                (timestamp, tracking_id, l_foot_y, r_foot_y, head_y) = data
                if tracking_id not in self.handlers:
                    self.handlers[tracking_id] = self.InputHandlerStamped()
                self.handlers[tracking_id].add_sample(timestamp, l_foot_y, r_foot_y, head_y)
            except Exception as e:
                print(e)
                print(data)
                exit()
        for handler in self.handlers.values():
            handler.evict_old()
        self.prune()

    def prune(self):
        for tracking_id, handler in list(self.handlers.items()):
            if len(handler.samples) == 0:
                del self.handlers[tracking_id]

    def is_jumping(self):
        if len(self.handlers) == 0:
            return False

        active_handler = min(self.handlers.values(), key=lambda h : h.created)
        return active_handler.is_jumping()

    def is_ducking(self):
        if len(self.handlers) == 0:
            return False
        
        active_handler = min(self.handlers.values(), key=lambda h : h.created)
        return active_handler.is_ducking()

    def __init__(self):
        self.handlers = {}
        self.pipe = None
               

def pipe_client():
    print("pipe client")
    quit = False
    input_handler = InputHandler()

    while not quit:
        try:
            handle = win32file.CreateFile(
                r'\\.\pipe\joint_states',
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None
            )
            res = win32pipe.SetNamedPipeHandleState(handle, win32pipe.PIPE_READMODE_MESSAGE, None, None)
            if res == 0:
                print(f"SetNamedPipeHandleState return code: {res}")
            while True:
                
                while win32pipe.PeekNamedPipe(handle, 0)[1] > 0:
                    resp = win32file.ReadFile(handle, 64*1024)
                    (hr, resp) = resp
                    resp = resp.decode("utf-16")
                    data = resp.split(",")
                    data = list(map(float, data))
                    (timestamp, tracking_id, l_foot_y, r_foot_y, head_y) = data
                    input_handler.add_sample(timestamp, l_foot_y, r_foot_y, head_y)
                input_handler.evict_old()
                time.sleep(2)
                print("iter")
        except pywintypes.error as e:
            if e.args[0] == 2:
                print("no pipe, trying again in a sec")
                time.sleep(1)
            elif e.args[0] == 109:
                print("broken pipe, bye bye")
                quit = True
            else:
                print(e)

if __name__ == "__main__":
    h = InputHandlerPipe()
    while True:
        h.update_state()
        time.sleep(2)
