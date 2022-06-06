#!/usr/bin/python3

from pyetcd import EtcdKeyNotFound, EtcdError

def test():
   try:
      e = EtcdError('''{"errorCode":100,"message":"Key not found","cause":"/samanamon2/data/test","index":192}''')
      raise EtcdKeyNotFound(e)
   except EtcdKeyNotFound as e:
      print(e)

test()