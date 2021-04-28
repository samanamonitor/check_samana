import urllib3
import json
from time import time

class Client:

  def __init__(self, customer_id, client_id, client_secret):
    self.customer_id = customer_id
    self.client_id = client_id
    self.client_secret = client_secret
    self.data = {
      'farm': {
        'TotalServers': 0,
        'LoadIndex': 0,
        'SessionCount': 0,
        'InMaintenanceMode': 0,
        'Registered': 0
      }
    }
    self.pool = urllib3.PoolManager()
    self.get_token()

  def get_token(self):
    token_url = "https://api-us.cloud.com/cctrustoauth2/%s/tokens/clients" % self.customer_id
    fields = {
      'grant_type': 'client_credentials',
      'client_id': self.client_id,
      'client_secret': self.client_secret
    }
    self.headers = {
      'Accept': 'application/json',
    }
    res = self.pool.request_encode_body('POST', token_url, fields=fields, headers=self.headers, encode_multipart=False)
    auth = json.loads(res.data.decode('UTF-8'))
    self.token = auth.get('access_token')
    self.expires = time() + float(auth.get('expires_in', '0'))
    self.headers['Authorization'] = "CwsAuth Bearer=%s" % self.token
    self.headers['Citrix-CustomerId'] = self.customer_id

  def get_data(self, url):
    if time() > self.expires:
      self.get_token()
    res = self.pool.request('GET', url, headers=self.headers)
    return json.loads(res.data.decode('UTF-8'))

  def get_sites(self):
    self.me = self.get_data('https://api-us.cloud.com/cvadapis/me')
    for customer in self.me['Customers']:
      if customer.get('Id') == self.customer_id:
        return customer.get('Sites')
    return None

  def get_desktopgroups(self, site_id):
    self.desktopgroups = self.get_data('https://api-us.cloud.com/cvadapis/%s/DeliveryGroups' % site_id).get('Items', None)
    self.data['desktopgroup'] = {}
    for dg in self.desktopgroups:
      self.data['desktopgroup'][dg['Name']] = {
        'TotalServers': 0,
        'LoadIndex': 0,
        'SessionCount': 0,
        'InMaintenanceMode': 0,
        'Registered': 0
      }

  def get_machines(self, site_id):
    if 'desktopgroup' not in self.data:
      self.get_desktopgroups(site_id)
    self.machines = self.get_data('https://api-us.cloud.com/cvadapis/%s/Machines' % site_id).get('Items', None)
    for m in self.machines:
      if m['DeliveryGroup'] is None: continue
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
