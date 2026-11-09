"""Bounded process-local success caches; keys are freshly computed byte digests."""
from collections import OrderedDict, namedtuple
import hashlib
import math
import struct
import sys
import threading

MISSING=object()
Info=namedtuple('CacheInfo','hits misses maxsize currsize')


def key(revision,*payloads):
    # Explicit lengths make the framing injective before SHA-256. These are
    # actual encoded inputs, never hashes supplied by a saved component.
    digest=hashlib.sha256()
    for payload in (revision.encode('utf8'),*payloads):
        digest.update(struct.pack('!Q',len(payload)));digest.update(payload)
    return digest.digest()


class SuccessCache:
    def __init__(self,maxsize):
        self.maxsize=maxsize;self.data=OrderedDict();self.hits=0;self.misses=0
        self.lock=threading.RLock()
    def get(self,key):
        with self.lock:
            value=self.data.get(key,MISSING)
            if value is MISSING:self.misses+=1
            else:self.hits+=1;self.data.move_to_end(key)
            return value
    def put(self,key,value):
        # Callers validate success before insertion. Values must be immutable.
        if type(key) is not bytes or type(value) not in (bool,float):raise TypeError('Invalid cache entry')
        if value is False or (type(value) is float and (not math.isfinite(value) or value<0)):
            raise ValueError('Only successful finite cache values may be retained')
        with self.lock:
            self.data[key]=value;self.data.move_to_end(key)
            while len(self.data)>self.maxsize:self.data.popitem(last=False)
    def clear(self):
        with self.lock:self.data.clear();self.hits=self.misses=0
    def info(self):
        with self.lock:return Info(self.hits,self.misses,self.maxsize,len(self.data))
    def retained_bytes(self):
        with self.lock:
            return sys.getsizeof(self.data)+sum(sys.getsizeof(k)+sys.getsizeof(v) for k,v in self.data.items())
