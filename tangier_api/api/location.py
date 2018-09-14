import zeep
import requests
import xmlmanip

from tangier_api import settings
from tangier_api import exceptions
from tangier_api import wrappers


class LocationConnection:
    def __init__(self, xml_string="", endpoint=settings.LOCATION_ENDPOINT, show_xml_request=False, show_xml_response=False):
        """

        :param xml_string: override the default xml, which is just <tangier method="schedule.request"/>
        :param endpoint: where the WSDL info is with routing info and SOAP API definitions
        """
        super(self.__class__, self).__init__()
        if not xml_string:
            self.base_xml = """<tangier version="1.0" method="location.request"></tangier>"""
        else:
            self.base_xml = xml_string
        # these two are used with @debug_options
        self.show_xml_request = show_xml_request
        self.show_xml_response = show_xml_response
        self.base_xml = xmlmanip.inject_tags(self.base_xml, admin_user=settings.TANGIER_USERNAME, admin_pwd=settings.TANGIER_PASSWORD)
        self.client = zeep.Client(endpoint, transport=zeep.transports.Transport(session=requests.Session()))

    @wrappers.handle_response
    @wrappers.debug_options
    def MaintainLocations(self, xml_string):
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
        # sites = {"site_id": site_id for i, site_id in enumerate(site_ids)}
        if not site_ids:
            site_ids = 'ALL_SITE_IDS'
        if not issubclass(site_ids.__class__, list):
            site_ids = [site_ids]
        tags = {f"location__{i}": {"action": "info", "__inner_tag": {"site_id": site_id}} for i, site_id in
                enumerate(site_ids)}
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

    def add_location(self, site_id=None, xml_string=None, name=None, short_name=None, **kwargs):
        """

        :param site_id: (str) id of site to be added
        :param xml_string: (xml string) overrides the default credential and/or location injection into base_xml
        :param kwargs: additional named properties to be provided in the creation request.
        :return: xml response string with an error message or info about a location.
        """
        if not (site_id and name and short_name):
            raise exceptions.APICallError(f'site_id, name, and short_name are all required key-word arguments.')
        tags = {f"location": {"action": "add", "__inner_tag": {"site_id": site_id,
                                                               "name": name, 'short_name': short_name, **kwargs}}}
        xml_string = xml_string if xml_string else self.base_xml
        xml_string = xmlmanip.inject_tags(xml_string, injection_index=2, locations="")
        xml_string = xmlmanip.inject_tags(xml_string, parent_tag="locations", **tags)
        return self.MaintainLocations(xml_string).encode('utf-8')

    def update_location(self, site_id=None, new_site_id=None, xml_string=None, name=None, short_name=None, **kwargs):
        """

        :param site_id: (str) id of site to be added
        :param new_site_id: (str) id of site to be renamed, if desired
        :param xml_string: (xml string) overrides the default credential and/or location injection into base_xml
        :param kwargs: additional named properties to be provided in the creation request.
        :return: xml response string with an error message or info about a location.
        """
        if not (site_id and name and short_name):
            raise exceptions.APICallError(f'site_id, name, and short_name are all required key-word arguments.')
        if new_site_id:
            tags = {f"location": {"action": "update",
                                  "__inner_tag": {"site_id": site_id, 'new_site_id': new_site_id,
                                                  "name": name, 'short_name': short_name, **kwargs}}}
        else:
            tags = {f"location": {"action": "update", "__inner_tag": {"site_id": site_id, "name": name,
                                                                      'short_name': short_name, **kwargs}}}
        xml_string = xml_string if xml_string else self.base_xml
        xml_string = xmlmanip.inject_tags(xml_string, injection_index=2, locations="")
        xml_string = xmlmanip.inject_tags(xml_string, parent_tag="locations", **tags)
        return self.MaintainLocations(xml_string).encode('utf-8')

    def delete_location(self, site_id=None, xml_string=None):
        """

        :param site_id: (str) id of site to be deleted
        :param xml_string: (xml string) overrides the default credential and/or location injection into base_xml
        :return: xml response string with an error message or info about a location.
        """
        if not site_id:
            raise exceptions.APICallError(f'site_id cannot be {site_id}')
        tags = {f"location": {"action": "delete", "__inner_tag": {"site_id": site_id}}}
        xml_string = xml_string if xml_string else self.base_xml
        xml_string = xmlmanip.inject_tags(xml_string, injection_index=2, locations="")
        xml_string = xmlmanip.inject_tags(xml_string, parent_tag="locations", **tags)
        return self.MaintainLocations(xml_string).encode('utf-8')