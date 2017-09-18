import configparser, os

from requests import Session

from zeep import Client
from zeep.transports import Transport

import xml.etree.ElementTree as ET

from . import helpers, xmlmanip

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


class ScheduleConnection:

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
        self.base_xml = xmlmanip.inject_tags(self.base_xml, user_name=TANGIER_USERNAME, user_pwd=TANGIER_PASSWORD)
        self.client = Client(endpoint, transport=Transport(session=Session()))

    def GetSchedule(self, xml_string=""):
        return self.client.service.GetSchedule(xml_string)

    def get_schedule(self, xml_string="", **tags):
        """
        :param xml_string: Can use this to override the default credential and/or schedule injection into base_xml
        :param tags: stuff to be injected into the schedule. ex: start_date="2017-05-01", end_date="2017-05-02"
        :return: xml response string with an error message or a schedule. Use tangier_api.helpers.pretty_print() to see it better.
        """
        xml_string = xml_string if xml_string else self.base_xml
        xml_string = xmlmanip.inject_tags(xml_string, injection_index=2, schedule="")
        xml_string = xmlmanip.inject_tags(xml_string, parent_tag="schedule", **tags)
        return self.GetSchedule(xml_string)


class ProviderConnection:

    def __init__(self, xml_string="", endpoint=SCHEDULE_ENDPOINT):
        """
        Injects credentials into <tanger/> root schema and
        :param xml_string: override the base xml, which is just <tangier method="schedule.request"/>
        :param endpoint: where the WSDL info is with routing info and SOAP API definitions
        """
        if not xml_string:
            self.base_xml = """<tangier version="1.0" method="provider.request"></tangier>"""
        else:
            self.base_xml = xml_string
        self.base_xml = xmlmanip.inject_tags(self.base_xml, admin_user=TANGIER_USERNAME,
                                                   admin_pwd=TANGIER_PASSWORD)
        self.client = Client(endpoint, transport=Transport(session=Session()))


    def MaintainProviders(self, xml_string=""):
        return self.client.service.MaintainProviders(xml_string)

    def get_provider_info(self, xml_string="", **tags):
        xml_string = xml_string if xml_string else self.base_xml
        xml_string = xmlmanip.inject_tags(xml_string, injection_index=2, providers="")
        xml_string = xmlmanip.inject_tags(xml_string, parent_tag="providers", **tags)
        return xml_string
        # self.MaintainProviders()
