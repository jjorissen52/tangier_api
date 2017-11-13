import asyncio, time, xmlmanip

from zeep.asyncio import AsyncTransport
from zeep import Client

from tangier_api import api


class AsyncScheduleConnection:
    def __init__(self, xml_string="", endpoint=api.SCHEDULE_ENDPOINT):
        """
        Async is actually slower than regular with Tangier. Don't use.
        :param xml_string: override the default xml, which is just <tangier method="schedule.request"/>
        :param endpoint: where the WSDL info is with routing info and SOAP API definitions
        """
        super(self.__class__, self).__init__()
        if not xml_string:
            self.base_xml = """<tangier version="1.0" method="schedule.request"></tangier>"""
        else:
            self.base_xml = xml_string
        self.base_xml = xmlmanip.inject_tags(self.base_xml, user_name=api.TANGIER_USERNAME, user_pwd=api.TANGIER_PASSWORD)
        self.loop = asyncio.get_event_loop()
        self.transport = AsyncTransport(self.loop, cache=None)
        self.client = Client(endpoint, transport=self.transport)
        self.good_responses = []
        self.bad_responses = []

    def GetSchedule(self, xml_string=""):
        """
        WSDL GetSchedule method
        :param xml_string: (xml str) fully formed xml string for GetSchedule request
        :return:
        """
        return self.client.service.GetSchedule(xml_string)

    def generate_request_list(self, start_date, end_date, site_ids):
        if not issubclass(site_ids.__class__, list):
            raise api.APICallError('site_ids must be a list or there is no point in an async call.')
        return [(start_date, end_date, site_id) for site_id in site_ids]

    def get_schedules(self, schedule_request_list, xml_string="", **tags):
        """
        :param xml_string: (xml string)overrides the default credential and/or schedule injection into base_xml
        :param tags: (kwargs) things to be injected into the request. ex: start_date="2017-05-01", end_date="2017-05-02"
        :return: xml response string with an error message or a schedule.
        """

        def handle_future(future):
            result.extend(future.result())

        base_xml_string = xml_string if xml_string else self.base_xml
        tasks, result = [], []
        for schedule_request in schedule_request_list:
            schedule_tags = {"site_id": schedule_request[2],
                             "start_date": schedule_request[0],
                             "end_date": schedule_request[1],
                             **tags}
            xml_string = base_xml_string
            xml_string = xmlmanip.inject_tags(xml_string, injection_index=2, schedule="")
            xml_string = xmlmanip.inject_tags(xml_string, parent_tag="schedule", **schedule_tags)
            tasks.append(self.GetSchedule(xml_string))
        future = asyncio.gather(*tasks, return_exceptions=True)
        future.add_done_callback(handle_future)
        self.loop.run_until_complete(future)
        self.loop.run_until_complete(self.transport.session.close())
        self.good_responses, self.bad_responses = HandleResponses.sort_bad_and_good(result, schedule_request_list)

        return result


class HandleResponses:
    @staticmethod
    def try_bad_again(result, request_list):
        connection = AsyncScheduleConnection()
        bad_indexes, bad_items, new_request_list = [], [], []
        for i, item in enumerate(result):
            if issubclass(item.__class__, Exception):
                bad_indexes.append(i)
                bad_items.append(item)
        for i in range(len(bad_indexes)):
            result.remove(bad_items[i])
            new_request_list.append(request_list[i])
        if new_request_list:
            print('re-attempting bad responses', len(new_request_list), len(request_list))
            result.extend(connection.get_schedules(new_request_list))
        return result

    @staticmethod
    def bad_to_new_request(results):
        bad_indexes, bad_items, new_request_list = [], [], []
        for i, result in enumerate(results):
            if issubclass(result['item'].__class__, Exception):
                new_request_list.append(result['request'])
        return new_request_list

    @staticmethod
    def sort_bad_and_good(result, request_list):
        bad, good = [], []
        for i, item in enumerate(result):
            if issubclass(item.__class__, Exception):
                bad.append({'index': i, "item": item, "request": request_list[i]})
            else:
                good.append({'index': i, "item": item, "request": request_list[i]})
        return good, bad

    @staticmethod
    def store_good(result, file_name):
        import pandas
        df = pandas.DataFrame()
        for i, item in enumerate(result):
            if not issubclass(item.__class__, Exception):
                temp_list = xmlmanip.XMLSchema(item.encode('utf-8')).search(siteid__contains='')
                good_list = list(map(lambda x: {'request': i, **x}, temp_list))
                if good_list:
                    temp_df = pandas.DataFrame(good_list)
                    df = df.append(temp_df)
        df.to_pickle(file_name)

    @staticmethod
    def get_values_list(response_list):
        values_list = []
        for item in response_list:
            values_list.extend(xmlmanip.XMLSchema(item.encode('utf-8')).search(siteid__contains=''))
        return values_list

