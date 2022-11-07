from .error import WRError
from .protocol import WRProtocol
import xml.etree.ElementTree as ET

class WMIQuery():
    base_uri='http://schemas.microsoft.com/wbem/wsman/1/wmi/root/cimv2/'
    def __init__(self, protocol=None, *args, **kwargs):
        if not isinstance(protocol, WRProtocol):
            raise Exception("Can only accept WRProtocol")
        if protocol is not None:
            self.p = protocol
        else:
            self.p = WRProtocol(*args, **kwargs)

    def get_class(self, class_name):
        try:
            self._class_data = self.p.get(self.base_uri + class_name)
        except WRError as e:
            error_code = e.fault_detail.find('wmie:MSFT_WmiError/wmie:error_Code', 
                self.p.xmlns)
            if error_code is not None and error_code.text == '2150859002':
                return self.enumerate_class(class_name)
            return e
        except Exception as e:
            return e

        self._root = ET.fromstring(self._class_data)
        xmldata=self._root.find('.//p:%s' % class_name, {'p': self.base_uri + class_name})
        data = self.wmixmltodict(xmldata, class_name)
        return data

    def wql(self, wql):
        return self.enumerate_class('*', wql=wql)

    def enumerate_class(self, class_name, en_filter=None, wql=None):
        self.resource_uri = self.base_uri + class_name
        self._class_data = self.p.enumerate(self.resource_uri, en_filter=en_filter, wql=wql)

        self._root = ET.fromstring(self._class_data)
        self._ec = self._root.find('s:Body/wsen:EnumerateResponse/wsen:EnumerationContext', 
            self.p.xmlns).text

        data = []
        while True:
            self.ec_data = self.p.pull(self.resource_uri, self._ec)
            self._pullresponse = ET.fromstring(self.ec_data)

            items = self._pullresponse.findall('.//wsen:Items/', 
                self.p.xmlns)
            for item in items:
                data += [self.wmixmltodict(item, class_name)]

            if self._pullresponse.find('s:Body/wsen:PullResponse/wsen:EndOfSequence', 
                self.p.xmlns) is not None:
                break
            _ec = self._pullresponse.find('s:Body/wsen:PullResponse/wsen:EnumerationContext', 
                self.p.xmlns)
            if _ec is None:
                raise WRError("Invalid EnumerationContext.")
            self._ec = _ec.text
        return data


    def wmixmltodict(self, data_root, class_name):
        data = {}
        nil = "{%s}nil" % self.p.xmlns['xsi']
        for i in data_root.findall('./'):
            tagname = i.tag.split('}')
            if len(tagname) > 1:
                tagname = tagname[1]
            else:
                tagname = tagname[0]
            if i.attrib.get(nil, 'false') == 'true':
                data[tagname] = None
            else:
                if i.text is not None:
                    data[tagname] = i.text
                else:
                    data[tagname]={}
                    for e in i.findall('./'):
                        # TODO: improve this to remove namespace
                        e_tagname=e.tag.split('}')
                        if len(e_tagname) > 1:
                            e_tagname = e_tagname[1]
                        else:
                            e_tagname = e_tagname[0]

                        data[tagname][e_tagname] = e.text
        return data

#class WMICommand(WinRMCommand):
#    def __init__(self, shell, class_name=None, class_filter=None):
#        WinRMCommand.__init__(self, shell)
#        self.class_name = class_name
#        self.class_filter = class_filter
#        self.interactive = self.class_name is not None
#
#    def run(self):
#        params = []
#        self.error = False
#        if self.class_name is not None:
#            params += [ 'PATH', self.class_name ]
#            if self.class_filter is not None:
#                params += [ 'WHERE', self.class_filter ]
#            params += [ 'GET', '/FORMAT:RAWXML' ]
#        self.command_id = self.shell.run_command('wmic', params)
#        self.receive()
#        if self.class_name is not None:
#            self.process_result()
#
#    def process_result(self):
#        try:
#            self.root = ET.fromstringlist(self.std_out.replace('\r','').split('\n')[:-1])
#        except Exception as e:
#            return
#        for property in self.root.findall(".//PROPERTY"):
#            n=property.attrib['NAME']
#            v=property.find("./VALUE")
#            self.data[n]=v.text if v is not None else None
#
#    def __repr__(self):
#        return "<%s interactive=%s code=%d%s%s error=%s std_out_bytes=%d std_err_bytes=%d>" % \
#            (self.__class__.__name__, self.interactive, self.code,
#                " class_name=%s" % self.class_name if self.class_name is not None else "",
#                " class_filter=%s" % self.class_filter if self.class_filter is not None else "",
#                self.error,
#                len(self.std_out), len(self.std_err))
#