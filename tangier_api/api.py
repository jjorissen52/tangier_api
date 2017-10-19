import re
import configparser, os

from requests import Session

from zeep import Client
from zeep.transports import Transport

import xml.etree.ElementTree as ET
import xmlmanip, pandas

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
        """
        WSDL GetSchedule method
        :param xml_string: (xml str) fully formed xml string for GetSchedule request
        :return:
        """
        return self.client.service.GetSchedule(xml_string)

    def get_schedule(self, xml_string="", **tags):
        """
        :param xml_string: (xml string)overrides the default credential and/or schedule injection into base_xml
        :param tags: (kwargs) things to be injected into the request. ex: start_date="2017-05-01", end_date="2017-05-02"
        :return: xml response string with an error message or a schedule.
        """
        xml_string = xml_string if xml_string else self.base_xml
        xml_string = xmlmanip.inject_tags(xml_string, injection_index=2, schedule="")
        xml_string = xmlmanip.inject_tags(xml_string, parent_tag="schedule", **tags)
        return self.GetSchedule(xml_string)


class APICallError(BaseException):
    pass


class ProviderConnection:

    def __init__(self, xml_string="", endpoint=PROVIDER_ENDPOINT):
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

    def get_provider_info(self, provider_ids=None, xml_string="", **tags):
        """
        Method to retrieve info on all providers corresponding to the list "provider_ids"
        :param provider_ids: (list) of all emp_ids corresponding to desired provider info
        :param xml_string: (xml string) overrides default xml string provided by the instantiation of the class object
        :param tags: (kwargs) things to be injected into the request. ex: start_date="2017-05-01", end_date="2017-05-02"
        :return:
        """
        if not provider_ids:
            raise APICallError("a list of provider_ids must be provided.")
        elif not isinstance(provider_ids, list):
            provider_ids = [provider_ids]
        xml_string = xml_string if xml_string else self.base_xml
        xml_string = xmlmanip.inject_tags(xml_string, injection_index=2, providers="")
        provider_dict = {}
        for i, provider_id in enumerate(provider_ids):
            provider_dict[f'provider__{i}'] = {"action": "info", "__inner_tag": {"emp_id": f"{provider_id}"}}
        xml_string = xmlmanip.inject_tags(xml_string, parent_tag="providers", **provider_dict)

        # return xml_string
        return self.MaintainProviders(xml_string).encode('utf-8')

    def provider_info_values_list(self, provider_ids=None):
        """
        Returns a Searchable List object (subclass of list) of all providers returned by get_provider_info
        :param provider_ids: (list) of all emp_ids corresponding to desired provider info
        :return: (SearchableList) of all providers returned by get_provider_info
        """
        xml_string = self.get_provider_info(provider_ids)
        schema = xmlmanip.XMLSchema(xml_string)
        # kind of hacky way to get every element with an emp_id tag
        provider_list = schema.search(emp_id__contains='')
        return provider_list


class LocationConnection:
    def __init__(self, xml_string="", endpoint=LOCATION_ENDPOINT):
        """

        :param xml_string: override the default xml, which is just <tangier method="schedule.request"/>
        :param endpoint: where the WSDL info is with routing info and SOAP API definitions
        """
        super(self.__class__, self).__init__()
        if not xml_string:
            self.base_xml = """<tangier version="1.0" method="location.request"></tangier>"""
        else:
            self.base_xml = xml_string
        self.base_xml = xmlmanip.inject_tags(self.base_xml, admin_user=TANGIER_USERNAME, admin_pwd=TANGIER_PASSWORD)
        self.client = Client(endpoint, transport=Transport(session=Session()))

    def MaintainLocations(self, xml_string=""):
        """
        WSDL GetLocation method
        :param xml_string: (xml str) fully formed xml string for GetLocation request
        :return:
        """
        return self.client.service.MaintainLocations(xml_string)

    def get_locations_info(self, site_ids=None, xml_string=None):
        """
        :param xml_string: (xml string) overrides the default credential and/or location injection into base_xml
        :return: xml response string with an error message or info about a location.
        """
        sites = {"site_id__{i}": site_id for i, site_id in enumerate(site_ids)}
        tags = {"location": {"action": "info", "__inner_tag": sites}}
        xml_string = xml_string if xml_string else self.base_xml
        xml_string = xmlmanip.inject_tags(xml_string, injection_index=2, locations="")
        xml_string = xmlmanip.inject_tags(xml_string, parent_tag="locations", **tags)
        return self.MaintainLocations(xml_string).encode('utf-8')

    def location_info_values_list(self, site_ids=None):
        """
        Returns a Searchable List object (subclass of list) of all locations returned by get_locations_info
        :param provider_ids: (list) of all emp_ids corresponding to desired locations info
        :return: (SearchableList) of all locations returned by get_locations_info
        """
        xml_string = self.get_locations_info(site_ids)
        schema = xmlmanip.XMLSchema(xml_string)
        # kind of hacky way to get every element with a site_id tag
        location_list = schema.search(site_id__contains='')
        return location_list


class ProviderReport(ProviderConnection):

    def __init__(self, file, *args, **kwargs):
        # TODO: isinstance
        if file.__class__.__name__ == pandas.DataFrame().__class__.__name__:
            self.df = file.copy()
        elif file.upper().endswith('.CSV'):
            self.df = pandas.read_csv(file)
        else:
            self.df = pandas.read_excel(file)
        super(ProviderReport, self).__init__(*args, **kwargs)

    def add_to_report(self, *args, key_column="provider_id"):
        """
        Adds the specified provider information to an excel or csv report according to NPI (emp_id)
        :param args: (list) of provider fields to be retrieved from tangier and added to the report
        :param key_column: (str) indicates the header name of the column that contains npis or emp_ids on the report
        :return: None
        """
        clean_ids = lambda x: int(float(x)) if not re.findall('[a-zA-Z]', f'{x}') else 0
        self.df[key_column] = self.df[key_column].apply(clean_ids)
        self.df[key_column] = self.df[key_column].astype(str)
        provider_ids = list(self.df[key_column].unique())
        info_list = self.provider_info_values_list(provider_ids=provider_ids)
        get_if_in_keys = lambda x, key: x[key] if key in x.keys() else ''
        columns_to_add = {arg: f'provider_{arg}' for arg in args}
        for column in columns_to_add.values():
            self.df[column] = ''
        original_index_name = self.df.index.name
        self.df = self.df.reset_index()
        for index, row in self.df.iterrows():
            provider_info = [*filter(lambda x: x.get("emp_id") == row[key_column], info_list)]
            if provider_info:
                for dict_key, df_column in columns_to_add.items():
                    self.df.loc[index, f'{df_column}'] = get_if_in_keys(provider_info[0], dict_key)

        columns = list(self.df.columns.values)
        reordered_columns = [key_column, *columns_to_add.values()]
        for col in reordered_columns:
            columns.remove(col)
        reordered_columns.extend(columns)
        self.df = self.df[[*reordered_columns]]
        self.df.set_index("index" if not original_index_name else original_index_name)
