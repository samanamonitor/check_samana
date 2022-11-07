import urllib3
import json
from time import time
import sys
from urllib3.exceptions import ReadTimeoutError

class Timer:
  def __init__(self, funcname, enable=False):
    self.funcname = funcname
    self.enable=enable

  def __enter__(self):
    if not self.enable: return
    self.start=time()
    print("%d - START %s" % (self.start, self.funcname), file=sys.stderr)
  def __exit__(self, type, value, traceback):
    if not self.enable: return
    self.end=time()
    print("%d - END %s - Total seconds %d" % (self.end, self.funcname, self.end-self.start), file=sys.stderr)


class Client:

  def __init__(self, customer_id, client_id, client_secret, max_retries=3, max_items=None, retry_delay=2, timing=False, read_timeout=15):
    self.customer_id = customer_id
    self.client_id = client_id
    self.client_secret = client_secret
    self._max_items=max_items
    self._max_retries=max_retries
    self._retry_delay=retry_delay
    self._timing = timing
    self._read_timeout = read_timeout
    self.data = {
      'farm': {
        'TotalServers': 0,
        'LoadIndex': 0,
        'SessionCount': 0,
        'InMaintenanceMode': 0,
        'Registered': 0,
        'epoch': int(time())
      }
    }
    self.base_url="https://api-us.cloud.com"
    self.pool = urllib3.PoolManager(timeout=self._read_timeout, headers={'Accept': 'application/json'})
    with Timer('get_token', self.timing):
      self.get_token()
    with Timer('get_sites', self.timing):
      self.sites = self.get_sites()
    self.set_site()

  def timing(self, funcname):
    yield
    end=time()

  def get_token(self):
    token_url = "%s/cctrustoauth2/%s/tokens/clients" % (self.base_url, self.customer_id)
    fields = {
      'grant_type': 'client_credentials',
      'client_id': self.client_id,
      'client_secret': self.client_secret
    }
    res = self.pool.request_encode_body('POST', token_url, fields=fields, encode_multipart=False)
    auth = json.loads(res.data.decode('ascii', errors='ignore'))
    self.token = auth.get('access_token', None)
    if self.token is None:
      raise Exception("Unable to get token from %s" % token_url)
    self.expires = time() + float(auth.get('expires_in', '0'))
    self.pool.headers['Authorization'] = "CwsAuth Bearer=%s" % self.token
    self.pool.headers['Citrix-CustomerId'] = self.customer_id
    self.pool.headers['User-Agent'] = "SamanaMonitor/1.0 Linux x64"

  def get_data(self, uri, **kwargs):
    if time() > self.expires:
      self.get_token()
    retries=self._max_retries
    while retries > 0:
      try:
        with Timer('get_data', self.timing):
          self._res = self.pool.request('GET', "%s/cvad/manage/%s" % (self.base_url, uri), headers=self.pool.headers, **kwargs)
      except ReadTimeoutError:
        print("Timed out. (read timeout=%d)" % self._read_timeout, file=sys.stderr)
        retries -= 1
        continue
      if self._res.status == 200:
        return json.loads(self._res.data.decode('ascii', errors='ignore'))
      elif self._res.status == 202:
        print("Waiting for job to finish")
        return None
      elif self._res.status == 429 or self._res.status == 503:
        err_data=json.loads(self._res.data.decode('ascii', errors='ignore'))
        retry_delay=err_data['parameters'].get('retryDelay', self._retry_delay)
        print("Retrying. Response data: %s" % err_data)
        time.sleep(retry_delay)
      else:
        raise Exception("Invalid data received from the API server %s %s" % (self._res.status, self._res.data))
      retries -= 1
    raise Exception("Maximum retries reached. Cannot get data")

  def get_sites(self):
    self.me = self.get_data('me')
    for customer in self.me['Customers']:
      if customer.get('Id') == self.customer_id:
        return customer.get('Sites')
    return None

  def set_site(self, name=None):
    for cust in self.me['Customers']:
      if cust['Id'] != self.customer_id: continue
      if len(cust['Sites']) == 1 and name is None:
        self.site_id=cust['Sites'][0].get('Id')
        self.pool.headers['Citrix-InstanceId'] = self.site_id
        return
      for s in cust['Sites']:
        if s['Name'] == name:
          self.site_id=s['Id']
          self.pool.headers['Citrix-InstanceId'] = self.site_id
          return

  def get_deliverygroups(self):
    if self.site_id is None or self.site_id == '':
      raise Exception("Need to define a site id first with set_site")
    data = self.get_data('DeliveryGroups')
    if 'Items' not in data:
      raise Exception("Invalid data received from Citrix Cloud getting desktopgroups %s" % (data))
    self.desktopgroups = data['Items']
    self.data['desktopgroup'] = {}
    for dg in self.desktopgroups:
      self.data['desktopgroup'][dg['Name']] = {
        'TotalServers': 0,
        'LoadIndex': 0,
        'SessionCount': 0,
        'InMaintenanceMode': 0,
        'Registered': 0,
        'epoch': int(time())
      }

  def get_machines(self):
    self.get_deliverygroups()
    self.data['farm']['epoch'] = int(time())
    self.data['hosts'] = {}
    self.machines = []
    fields = {}
    if self._max_items is not None:
      fields['limit'] = self._max_items

    while True:
      data = self.get_data('Machines', fields=fields)
      if 'Items' not in data:
        raise Exception("Invalid data received from Citrix Cloud getting machines %s" % (data))
      self.machines += data['Items']
      if "ContinuationToken" in data:
        fields['ContinuationToken'] = data['ContinuationToken']
      else:
        break

    for m in self.machines:
      m['epoch'] = int(time())
      m['DesktopGroupName'] = 'None' if m['DeliveryGroup'] is None else m['DeliveryGroup']['Name']
      if m['DeliveryGroup'] is None: 
        continue
      self.data['hosts'][m['DnsName'].lower()] = m
      dg_name = m['DeliveryGroup']['Name']
      dg = self.data['desktopgroup'][dg_name]
      farm = self.data['farm']
      dg['TotalServers'] += 1
      farm['TotalServers'] += 1
      dg['SessionCount'] += m['SessionCount']
      farm['SessionCount'] += m['SessionCount']
      if m['RegistrationState'] == 'Registered' and m['InMaintenanceMode'] is False:
        load = m['LoadIndex'] if m['LoadIndex'] is not None else 0
        dg['LoadIndex'] += load
        farm['LoadIndex'] += load
      else:
        dg['LoadIndex'] += 10000
        farm['LoadIndex'] += 10000
      if m['RegistrationState'] == 'Registered':
        dg['Registered'] += 1
        farm['Registered'] += 1
      if m['InMaintenanceMode'] is True:
        dg['InMaintenanceMode'] += 1
        farm['InMaintenanceMode'] += 1
    for dg in self.data['desktopgroup']:
      if self.data['desktopgroup'][dg]['TotalServers'] > 0:
        self.data['desktopgroup'][dg]['LoadIndex'] /= self.data['desktopgroup'][dg]['TotalServers']
      else:
        self.data['desktopgroup'][dg]['LoadIndex'] = 10000
