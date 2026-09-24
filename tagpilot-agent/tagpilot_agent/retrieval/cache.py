"""线程安全、有界进程缓存；只保存不可变发布证据的副本。"""
from collections import OrderedDict
from copy import deepcopy
from threading import RLock
import hashlib

class LRU:
    def __init__(self, capacity=256):
        self.capacity=capacity; self.data=OrderedDict(); self.lock=RLock()
    def get(self,key):
        with self.lock:
            if key not in self.data:return None
            self.data.move_to_end(key)
            return deepcopy(self.data[key])
    def put(self,key,value):
        with self.lock:
            self.data[key]=deepcopy(value);self.data.move_to_end(key)
            while len(self.data)>self.capacity:self.data.popitem(last=False)


def eligible_hash(ids):
    return hashlib.sha256('\n'.join(sorted(str(i) for i in ids)).encode()).hexdigest()

cards_cache=LRU()
details_cache=LRU(1024)
