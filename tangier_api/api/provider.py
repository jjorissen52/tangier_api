import zeep
import requests
import xmlmanip

from tangier_api import settings
from tangier_api import exceptions


class ProviderConnection:

    def __init__(self, xml_string="", endpoint=settings.PROVIDER_ENDPOINT):
        """
        Injects credentials into <tanger/> root schema and

        :param xml_string: override the base xml, which is just <tangier method="schedule.request"/>
        :param endpoint: where the WSDL info is with routing info and SOAP API definitions
        """
        if not xml_string:
            self.base_xml = """<tangier version="1.0" method="provider.request"></tangier>"""
        else:
            self.base_xml = xml_string
        self.base_xml = xmlmanip.inject_tags(self.base_xml, admin_user=settings.TANGIER_USERNAME,
                                             admin_pwd=settings.TANGIER_PASSWORD)
        self.client = zeep.Client(endpoint, transport=zeep.transports.Transport(session=requests.Session()))

    def MaintainProviders(self, xml_string=""):
        return self.client.service.MaintainProviders(xml_string)

    def get_provider_info(self, provider_ids=None, use_primary_keys=True, all_providers=True, xml_string="", **tags):
        """
        Method to retrieve info on all providers corresponding to the list "provider_ids"

        :param provider_ids: (list) of all emp_ids corresponding to desired provider info
        :param use_primary_keys: (bool) indicates whether provider_ids should be treated as emp_id or provider_primary_key
        :param all_providers: (bool) indicates whether to return data on all existing providers
        :param xml_string: (xml string) overrides default xml string provided by the instantiation of the class object
        :param tags: (kwargs) things to be injected into the request. ex: start_date="2017-05-01", end_date="2017-05-02"
        :return:
        """
        if not provider_ids and not all_providers:
            raise exceptions.APICallError("You must provide either a list of provider_ids or set all_providers=True.")
        elif not isinstance(provider_ids, list):
            provider_ids = [provider_ids]
        xml_string = xml_string if xml_string else self.base_xml
        xml_string = xmlmanip.inject_tags(xml_string, injection_index=2, providers="")
        provider_dict = {}
        id_label = "provider_primary_key" if use_primary_keys else "emp_id"
        if not all_providers:
            for i, provider_id in enumerate(provider_ids):
                provider_dict[f'provider__{i}'] = {"action": "info", "__inner_tag": {id_label: f"{provider_id}"}}
        else:
            provider_dict[f'provider'] = {"action": "info", "__inner_tag": {id_label: "ALL"}}
        xml_string = xmlmanip.inject_tags(xml_string, parent_tag="providers", **provider_dict)

        # return xml_string
        return self.MaintainProviders(xml_string).encode('utf-8')

    def provider_info_values_list(self, use_primary_keys=True, **kwargs):
        """
        Wrapper for get_provider info which converts the xml response into a list of dicts
        """
        xml_string = self.get_provider_info(**kwargs)
        schema = xmlmanip.XMLSchema(xml_string)
        if kwargs.get('all_providers'):
            id_label = 'provider_primary_key'
        else:
            id_label = "provider_primary_key" if use_primary_keys else "emp_id"
        # using contains method here is kind of hacky way to get every element with an {id_label} tag, basically I'm
        # just checking to see that the label even exists
        label_dict = {f"{id_label}__contains": ""}
        provider_list = schema.search(**label_dict)
        return provider_list
