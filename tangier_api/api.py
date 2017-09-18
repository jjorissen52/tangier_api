import configparser, os

from requests import Session

from zeep import Client
from zeep.transports import Transport

from xmlmanip import XMLSchema

import xml.etree.ElementTree as ET

from . import helpers

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INTERFACE_CONF_FILE = os.environ.get('INTERFACE_CONF_FILE')
INTERFACE_CONF_FILE = os.path.join(INTERFACE_CONF_FILE) if INTERFACE_CONF_FILE else os.path.join(PROJECT_DIR,
                                                                                                 'tangier.conf')

config = configparser.ConfigParser()
config.read(INTERFACE_CONF_FILE)

TANGIER_USERNAME = config.get('tangier', 'username')
TANGIER_PASSWORD = config.get('tangier', 'password')
SCHEDULE_ENDPOINT = config.get('tangier', 'schedule_endpoint')
PROVIDER_ENDPOINT = config.get('tangier', 'provider_endpoint')
LOCATION_ENDPOINT = config.get('tangier', 'location_endpoint')
TESTING_SITE = config.get('tangier', 'testing_site')


class Helpers:
    class Meta:
        abstract = True

    """
    Helper Methods
    """

    def _search_schema(self, schema_str, show_all=True, **kwarg):
        schema = XMLSchema(schema_str)
        paths = schema.locate(**kwarg)
        items = [schema.retrieve('__'.join(path.split('__')[:-1])) for path in paths]
        kwarg_key = list(kwarg.keys())[0].split('__')[0]
        try:
            sorted_list = sorted(items, key=lambda x: int(x[kwarg_key])) if show_all else \
                sorted(items, key=lambda x: int(x[kwarg_key]))[-1]
        except IndexError:  # happens when there are no results in the search
            sorted_list = None
        return sorted_list


"""
        Injects a new tag with the specified content at the indicated parent and index
        :param xml_string: xml_string where the tags are to be injected
        :param parent_tag: name of the parent tag where indicated tags are to be injected (leave blank for injecting to root tag)
        :param injection_index: indicates the index of where the tags will be inserted into their parents. 0 for first, 1 for second, so on
        :param tags: kwargs indicating tags and text of tags:
                     * thing="1" --->
                            <thing>1</thing>,
                     * provider={"text":"some text", "action":"info"} --->
                            <provider action="info">some text</provider>
                     * provider__1={"text":"some text", "action":"info"},
                       provider__2={"text":"other text", "action":"info"} --- >
                            <provider action="info">some text</provider>
                            <provider action="info">other text</provider>
        :return: modified xml_string with newly injected tags
        """

class BaseConnection(Helpers):
    """
        Forms the base connection for interacting with Tangier's API
    """

    @staticmethod
    def inject_tags(xml_string, parent_tag="", injection_index=0, **tags):
        """
        Injects a new tag with the specified content at the indicated parent and index
        :param xml_string: xml_string where the tags are to be injected
        :param parent_tag: name of the parent tag where indicated tags are to be injected (leave blank for injecting to root tag)
        :param injection_index: indicates the index of where the tags will be inserted into their parents. 0 for first, 1 for second, so on
        :param tags: kwargs indicating tags and text of tags:
                     * thing="1" --->
                            <thing>1</thing>,
                     * provider={"text":"some text", "action":"info"} --->
                            <provider action="info">some text</provider>
                     * provider__1={"text":"some text", "action":"info"},
                       provider__2={"text":"other text", "action":"info"} --- >
                            <provider action="info">some text</provider>
                            <provider action="info">other text</provider>
        :return: modified xml_string with newly injected tags
        """
        schema = ET.fromstring(xml_string)
        if not parent_tag:
            parent = schema
        elif schema.find(parent_tag) is not None:
            parent = schema.find(parent_tag)
        else:
            raise helpers.BadSchemaError(f"No <{parent_tag}/> tag included in the given schema.")
        for i, kword in enumerate(tags.keys()):
            if parent.find(kword) is not None:
                pass
            else:
                if isinstance(tags[kword], dict):
                    if 'text' in tags[kword].keys():
                        text = tags[kword].pop('text')
                    else:
                        text = ""
                    # the split in the line below allows the user to add multiple instances of the same tag.
                    # necessary because python doesn't allow repetition of kwargs, and xml sometimes requires
                    # repetition of tags.
                    new_tag = ET.Element(kword.split('__')[0], tags[kword])
                elif isinstance(tags[kword], str):
                    text = tags[kword]
                    new_tag = ET.Element(kword.split('__')[0])
                else:
                    raise TypeError(f"Passed kwarg '{kword} is {type(tags[kword])}. Must be str or dict.'")
                new_tag.text = text
                parent.insert(injection_index, new_tag)
                injection_index += 1
        try:
            schema_str = ET.tostring(schema)
        except TypeError as e:
            raise TypeError(f"One of tags you attempted to inject is not a supported type: {e}")

        return schema_str


class ScheduleConnection(BaseConnection):

    def __init__(self, xml_string="", endpoint=SCHEDULE_ENDPOINT):
        """

        :param xml_string: override the default xml, which is just <tangier method="schedule.request"/>
        :param endpoint: where the WSDL info is with routing info and SOAP API definitions
        """
        super(self.__class__, self).__init__()
        if not xml_string:
            self.base_xml = """<tangier version="1.0" method="schedule.request"></tangier>"""
        else:
            self.base_xml = xml_string
        self.base_xml = BaseConnection.inject_tags(self.base_xml, user_name=TANGIER_USERNAME, user_pwd=TANGIER_PASSWORD)
        self.client = Client(endpoint, transport=Transport(session=Session()))


    def GetSchedule(self, xml_string="", **tags):
        """

        :param xml_string: Can use this to override the default credential and/or schedule injection into base_xml
        :param tags: stuff to be injected into the schedule. ex: start_date="2017-05-01", end_date="2017-05-02"
        :return: xml response string with an error message or a schedule. Use tangier_api.helpers.pretty_print() to see it better.
        """
        xml_string = xml_string if xml_string else self.base_xml
        xml_string = BaseConnection.inject_tags(xml_string, injection_index=2, schedule="")
        xml_string = BaseConnection.inject_tags(xml_string, parent_tag="schedule", **tags)
        return self.client.service.GetSchedule(xml_string)


class ProviderConnection(BaseConnection):

    def __init__(self, xml_string="", endpoint=SCHEDULE_ENDPOINT):
        """
        Injects credentials into <tanger/> root schema and
        :param xml_string: override the base xml, which is just <tangier method="schedule.request"/>
        :param endpoint: where the WSDL info is with routing info and SOAP API definitions
        """
        super(self.__class__, self).__init__()
        if not xml_string:
            self.base_xml = """<tangier version="1.0" method="provider.request"></tangier>"""
        else:
            self.base_xml = xml_string
        self.base_xml = BaseConnection.inject_tags(self.base_xml, admin_user=TANGIER_USERNAME,
                                                   admin_pwd=TANGIER_PASSWORD)
        self.client = Client(endpoint, transport=Transport(session=Session()))


    def MaintainProviders(self, xml_string=""):
        """

        :param xml_string: fully formed xml for a Maintain Providers request
        :return: xml response string for MaintainProviders request. Use tangier_api.helpers.pretty_print() to see it better.
        """
        return self.client.service.MaintainProviders(xml_string)

    def get_provider_info(self, xml_string="", **tags):
        xml_string = xml_string if xml_string else self.base_xml
        xml_string = BaseConnection.inject_tags(xml_string, injection_index=2, providers="")
        xml_string = BaseConnection.inject_tags(xml_string, parent_tag="providers", **tags)
        return xml_string
        # self.MaintainProviders()
