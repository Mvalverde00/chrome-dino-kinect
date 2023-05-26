import time
import threading
import requests

class AsyncPoster():

    def __init__(self):
        self.last_reported = 0 # Last value sent
        self.stamp = round(time.time() * 1000.0) # When the value was reported
        self.delay = 750 # ms.


    def reset(self):
        self.last_reported = 0
        self.stamp = round(time.time() * 1000.0)


    def __send_req(self, dist):
        # It's really an Async Getter. Oops.
        requests.get("http://137.184.17.37/move/" + str(dist))
        

    def try_post(self, curr_val):
        now = round(time.time() * 1000.0)

        if now - self.stamp < self.delay:
            return

        self.stamp = now
        delta = curr_val - self.last_reported
        self.last_reported = curr_val

        # It can only ever be less than 0 if the player died. Ignore that.
        if delta > 0:
            threading.Thread(target=self.__send_req, args=[delta]).start()

    def force_post(self, curr_val):
        self.stamp = round(time.time() * 1000.0)
        delta = curr_val - self.last_reported
        self.last_reported = curr_val

        # It can only ever be less than 0 if the player died. Ignore that.
        if delta > 0:
            threading.Thread(target=self.__send_req, args=[delta]).start()

        
