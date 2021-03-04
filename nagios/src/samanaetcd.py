import urllib3
import json

class EtcdKeyNotFound(Exception):
    def __init__(self, message=None, payload=None):
        self.message = message if message is not None else 'Key not found'
        self.cause = payload.get('cause')

    def __str__(self):
        return "%s : %s" % (self.message, self.cause)

class Client():
    def __init__(self, host='127.0.0.1', port=4001, version_prefix='/v2', read_timeout=60, allow_redirect=True, protocol='http', cert=None, ca_cert=None, allow_reconnect=False, use_proxies=False, expected_cluster_id=None, per_host_pool_size=10):
        self.http = urllib3.PoolManager()
        self.host = host
        self.port = port
        self.version_prefix = version_prefix
        self.protocol = protocol

    def get(self, key):
        r = self.http.request('GET', '%s://%s:%s/%s/keys/%s' %(self.protocol, self.host, self.port, self.version_prefix, key))
        if r.status != 200: raise EtcdKeyNotFound(payload={'errorCode': 100, 'index': 0, 'message': 'Key not found', 'cause': key})
        data = json.loads(r.data)
        return EtcdResult(action=data['action'], node=data['node'])

class EtcdResult():
    def __init__(self, action=None, node=None, prevNode=None, **kwdargs):
        self.action = action
        if action == 'get':
            self.newKey = False
        else:
            self.newKey = True
        self.dir = True if "dir" in node else False
        self.ttl = None
        self.key = node['key']
        self._children = node.get('nodes')
        self.createdIndex = node.get('createdIndex')
        self.modifiedIndex = node.get('modifiedIndex')
        self.expiration = None
        self.etcd_index = 0
        self.value = node.get('value')
