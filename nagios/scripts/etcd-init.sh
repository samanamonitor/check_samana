#!/bin/bash

etcdctl set /samanamonitor/config/global \
    '{"eventminutes":10,"eventmax":11,"eventlevelmax":3,"eventlist":["System","Application"]}'
etcdctl set /samanamonitor/config/storefront-example \
    '{"eventminutes":10,"eventmax":11,"eventlevelmax":3,"eventlist":["System","Application", "Citrix Delivery Services"]}'
