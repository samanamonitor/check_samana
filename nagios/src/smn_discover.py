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
    hosts = c.get("/samanamonitor/ctx_data/%s/computer" % ddc_name)
    auto=auto_init()
    auto_hosts = auto.get_effective_hosts()
    ctx_hosts=[]
    for h in hosts.leaves:
        try:
            hd = c.get("%s/data" % h.key)
            hostdata = json.loads(hd.value)
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

def new_ctx_host(hostdata, role, ddc_name, method="fqdn"):
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

POWERSTATE_UNMANAGED    = 0
POWERSTATE_UNKNOWN      = 1
POWERSTATE_UNAVAILABLE  = 2
POWERSTATE_OFF          = 3
POWERSTATE_ON           = 4
POWERSTATE_SUSPENDED    = 5
POWERSTATE_TURNINGON    = 6
POWERSTATE_TURNINGOFF   = 7
POWERSTATE_SUSPENDING   = 8
POWERSTATE_RESUMING     = 9
POWERSTATE_NOTSUPPORTED = 10

def get_hosts_in_ctx_site(ddc_name):
    '''Returns a dict that conatins hosts in the Citrix Site
        Dict is started with two keys with empty sets: all and disable
        The tags defined in each host is validated for SAMM_ tags
        and keys are created for each of these tags
    '''
    ctx_hosts={'all': set(), 'disable': set(), 'remove': set()}
    try:
        hosts = c.get("/samanamonitor/ctx_data/%s/computer" % ddc_name)
    except Exception:
        return []
    for i in hosts.leaves:
        try:
            hdatajson = c.get("%s/data" % i.key)
            hdata = json.loads(hdatajson.value)
        except Exception as e:
            pass
        fqdn = i.key.split("/")[-1]
        ctx_hosts['all'].add(fqdn)
        for t in hdata['Tags']:
            tag= t.lower()
            if tag[:5] != "samm_": continue
            sammtag = tag[5:]
            if sammtag not in ctx_hosts:
                ctx_hosts[sammtag] = set()
            ctx_hosts[sammtag].add(fqdn)
        if hdata['PowerState'] == POWERSTATE_OFF \
            or hdata['PowerState'] == POWERSTATE_TURNINGOFF \
            or hdata['PowerState'] == POWERSTATE_RESUMING \
            or hdata['PowerState'] == POWERSTATE_TURNINGON \
            or hdata['PowerState'] == POWERSTATE_SUSPENDED \
            or hdata['PowerState'] == POWERSTATE_SUSPENDING:
            ctx_hosts['disable'].add(fqdn)
    return ctx_hosts

def get_hosts_in_samm(ddc_name):
    '''Returns a dict that conatins hosts in SAMM
        Dict is started with two keys with empty sets: all and disable
    '''
    hg=Hostgroup.objects.get_by_shortname("autohostgroup")
    ahg=hg.get_effective_hosts()
    samm_ctx_hosts={'all': set(), 'remove': set()}
    for i in ahg:
        ddc=i.get_macro("$_HOSTHOME_DDC$")
        if ddc == ddc_name:
            fqdn = i.get_macro("$_HOSTID$")
            samm_ctx_hosts['all'].add(fqdn)
            if i.register == 0:
                samm_ctx_hosts['remove'].add(fqdn)
    return samm_ctx_hosts

def get_name(data):
    name = ""
    return name

def remove_hosts(hosts):
    for h in hosts:
        pass

def add_hosts(hosts, role, ddc_name):
    for fqdn in hosts:
        hostdata_j = c.get("/samanamonitor/ctx_data/%s/computer/%s/data" % (ddc_name, fqdn))
        host_data = json.loads(hostdata_j.value)
        if "Name" in host_data:
            host_name=host_data['Name'].replace('\\', '_')
        elif "MachineName" in host_data:
            host_name=host_data['MachineName'].replace('\\', '_')
        hg_alias = host_data.get('DesktopGroupName').lower()
        hg_name = "ctx-%s" % hg_alias.replace(' ', '_')
        add_ctx_hg(hg_name, hg_alias)
        host.address=host_data.get('DNSName').lower()
        host.set_attribute('use', role)
        host.set_macro('$_HOSTHOME_DDC$', ddc_name)
        host.set_macro('$_HOSTEARGS$', '-idMethod fqdn')
        host.set_macro('$_HOSTID$', host.address)
        host.add_to_hostgroup(hg_name)


def process_hosts(ddc_name):
    '''Receives a DDC name, collects the hosts from the farm and
        the hosts configured in SAMM and calculates which hosts
        need to be disabled, unregistered or removed from SAMM
    '''
    change = False
    ctx_site_hosts=get_hosts_in_ctx_site(ddc_name)
    samm_ctx_hosts=get_hosts_in_samm(ddc_name)
    hosts_to_remove     = samm_ctx_hosts['all'] - ctx_site_hosts['all']
    change |= remove_hosts(hosts_to_remove)
    hosts_to_add        = ctx_site_hosts['all'] - samm_ctx_hosts['all']
    change |= add_hosts(hosts_to_add)
    hosts_to_unregister = ctx_site_hosts['remove']
    change |= unregister_hosts(hosts_to_unregister)
    hosts_to_register   = ctx_site_hosts['all'] - ctx_site_hosts['remove']
    change |= unregister_hosts(hosts_to_register)
    hosts_to_disable    = ctx_site_hosts['disable']
    disable_hosts(hosts_to_disable)
    hosts_to_enable     = ctx_site_hosts['all'] - ctx_site_hosts['disable']
    enable_hosts(hosts_to_enable)
    return change

def main(argv):
    pass

if __name__ == '__main__':
    main(argv)
