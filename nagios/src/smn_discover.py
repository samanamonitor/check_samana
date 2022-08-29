#!/usr/bin/python3

from pynag.Control import daemon
from samana.etcd import Client
import json
from pynag.Model import Hostgroup, Host
from hashlib import md5, sha256
from sys import argv

nagios_config_path='/usr/local/nagios/etc'
nagios_objects='%s/objects' % nagios_config_path
auto_objects='%s/environment/auto-objects.cfg' % nagios_objects
nagios_bin='/usr/local/nagios/bin/nagios'
nagios_cfg='/usr/local/nagios/etc/nagios.cfg'
ddc_name='smnnovctxddc1'


c = Client(port=2379)

def auto_init():
    try:
        autohg = Hostgroup.objects.get_by_shortname('autohostgroup')
    except KeyError:
        autohg = Hostgroup(filename=auto_objects)
        autohg.hostgroup_name='autohostgroup'
        autohg.register=0
        autohg.save()
    return autohg


def remove_hosts(ddc_name):
    hosts = c.get("/samanamonitor/ctx_data/%s/hosts" % ddc_name)
    auto=auto_init()
    auto_hosts = auto.get_effective_hosts()
    ctx_hosts=[]
    for h in hosts.leaves:
        try:
            hostdata = json.loads(h.value)
        except:
            continue
        host_name = "%s-A" % hostdata['DNSName'].split('.')[0].upper()
        ctx_hosts += [ host_name ]
        if "SAMM_Remove" not in hostdata['Tags']:
            continue

        r=Host.objects.get_by_shortname(host_name)
        if r is not None:
            if r not in auto_hosts:
                continue
            r.delete()
    for h in auto_hosts:
        if h.host_name in ctx_hosts:
            continue
        h.delete()

def add_ctx_hg(hg_name, alias):
    try:
        dg_hg = Hostgroup.objects.get_by_shortname(hg_name)
    except KeyError:
        dg_hg = Hostgroup(filename=auto_objects)
        dg_hg.hostgroup_name = hg_name
        dg_hg.alias = alias
        autohg = auto_init()
        autohg.attribute_appendfield('hostgroup_members', dg_hg.get_shortname())
        dg_hg.save()
        autohg.save()
    return dg_hg

def new_ctx_host(hostdata, role, method="fqdn"):
    if "SAMM_Remove" in hostdata['Tags']:
        return None
    hg_alias = hostdata['DesktopGroupName'].lower()
    hg_name = "ctx-%s" % hg_alias.replace(' ', '-')
    add_ctx_hg(hg_name, hg_alias)
    host_name = "%s-A" % hostdata['DNSName'].split('.')[0].upper()
    try:
        host = Host.objects.get_by_shortname(host_name)
    except KeyError:
        host = Host(filename=auto_objects)
    host.host_name=host_name
    host.address=hostdata['DNSName'].lower()
    host.set_attribute('use', role)
    host.set_macro('$_HOSTHOME_DDC$', ddc_name)
    if method == "fqdn":
        host_id = host.address
    elif method == "md5":
        host_id = md5(host.address.encode('utf8')).hexdigest().upper()
    else:
        return None
    host.set_macro('$_HOSTEARGS$', '-idMethod %s' % method)
    host.set_macro('$_HOSTID$', host_id)
    host.add_to_hostgroup(hg_name)
    return host

def add_hosts(ddc_name, role='role-citrix3-sh'):
    hosts = c.get("/samanamonitor/ctx_data/%s/hosts" % ddc_name)
    for h in hosts.leaves:
        try:
            hostdata = json.loads(h.value)
        except:
            continue
        host=new_ctx_host(hostdata, role)
        if host is None:
            continue
        host.save()

def reload():
    d = daemon(nagios_bin=nagios_bin, nagios_cfg=nagios_cfg)
    if d.verify_config():
        return d.reload()
    return -1

def get_farm_db():
    # run Get-AcctDBConnection and output will be:
    # Server=smnnovctxddc1\sqlexpress;Initial Catalog=CitrixSAMANASite;Integrated Security=True
    data="Server=smnnovctxddc1\\sqlexpress;Initial Catalog=CitrixSAMANASite;Integrated Security=True"
    data.split(';')[0].split('=')[1]


def main(argv):
    pass

if __name__ == '__main__':
    main(argv)
