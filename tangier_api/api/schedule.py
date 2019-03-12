import re
import datetime
import pandas
import numpy
import xmlmanip

from zeep import Client
from zeep.transports import Transport
from requests import Session

from tangier_api import settings
from tangier_api.exceptions import APICallError


class ScheduleConnection:
    in_date_format = "%m/%d/%Y"  # API sometimes returns dates in this format
    datetime_format = "%Y-%m-%dT%H:%M:%S"  # standard ISOformat datetime
    date_format = "%Y-%m-%d"  # API requires dates as arguments in this format
    time_format = "%I:%M %p"  # API sometimes returns times in this format
    full_date_pattern = "\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2} (AM|PM)"
    full_date_regex = re.compile(full_date_pattern)

    def __init__(self, xml_string="", site_file=None, site_id_column_header='site_id', testing=False,
                 endpoint=settings.SCHEDULE_ENDPOINT, debug=False):
        """
        Initializes the ScheduleConnection. This method attempts to authenticate the connection, pulls site_ids from the site_id file, and determines WSDL definition info

        :param xml_string: override the default xml, which is just <tangier method="schedule.request"/>
        :param site_file: (str) fully qualified path to xlsx or csv document containing all tangier site ids
        :param site_id_column_header: (str) header name of column containing site ids in site_file
        :param endpoint: where the WSDL info is with routing info and SOAP API definitions
        """

        if not xml_string:
            self.base_xml = """<tangier version="1.0" method="schedule.request"></tangier>"""
        else:
            self.base_xml = xml_string
        if site_file:
            if site_file.endswith('.xlsx'):
                df = pandas.read_excel(site_file)
            elif site_file.endswith('.csv'):
                df = pandas.read_csv(site_file)
            else:
                df = pandas.DataFrame()
                print('Did not read site file; must be a csv or xlsx document.')

            if not df.empty and site_id_column_header in list(df.columns):
                if testing:
                    self.site_ids = list(numpy.random.choice(df[site_id_column_header], 20, replace=False))
                else:
                    self.site_ids = list(df[site_id_column_header])
            elif df.emtpy:
                self.site_ids = []
            else:
                print('Site ids must be in a column with the header "{0}"'.format(site_id_column_header))

        self.base_xml = xmlmanip.inject_tags(self.base_xml, user_name=settings.TANGIER_USERNAME, user_pwd=settings.TANGIER_PASSWORD)
        self.client = Client(endpoint, transport=Transport(session=Session()))
        self.saved_schedule = None
        self.debug = debug

    def GetSchedule(self, xml_string=""):
        """
        WSDL GetSchedule method

        :param xml_string: (xml str) fully formed xml string for GetSchedule request
        :return:
        """
        return self.client.service.GetSchedule(xml_string).encode('utf-8')

    def _extract_shifts(self, shifts, in_date_format=in_date_format, out_date_format=date_format):
        shifts_date_str = shifts["@shiftdate"]
        shifts_date_in = datetime.datetime.strptime(shifts_date_str, in_date_format)
        shifts_date = shifts_date_in.strftime(out_date_format)
        if issubclass(shifts['shifts']['shift'].__class__, list):
            shifts_list = shifts['shifts']['shift']
        else:
            shifts_list = [shifts['shifts']['shift']]

        def to_iso(shift_time, shifts_date):
            return self._time_and_date_to_iso(shift_time, shifts_date)

        shifts_with_start_dates = list(map(lambda x: {"shift_start_date": to_iso(x['actualstarttime'],
                                                                                 shifts_date),
                                                      **x},
                                           shifts_list))

        def add_end_date(shift):
            return ScheduleConnection._add_end_date('shift_start_date', 'reportedminutes', shift)

        return list(map(lambda x: add_end_date(x), shifts_with_start_dates))

    @staticmethod
    def _add_end_date(start_datetime_key, duration_key, shift, start_datetime_format=datetime_format):
        start_datetime_str = shift[start_datetime_key].strip()
        start_datetime = datetime.datetime.strptime(f'{start_datetime_str}', f'{start_datetime_format}')
        duration_str = shift[duration_key].strip()
        duration = datetime.timedelta(minutes=int(float(duration_str)))
        end_datetime = start_datetime + duration
        end_datetime_str = end_datetime.isoformat()
        return {"shift_end_date": end_datetime_str, **shift}

    def _time_and_date_to_iso(self, time, date):
        # Older Tangier API servers return just %I:%M %p while newer ones have been updated to use
        # %m/%d/%Y %I:%M %p. This is is not consistent across API v1.0, unfortunately so
        # we have to check.
        if self.full_date_regex.match(time):
            datetime_str = time
            datetime_fmt = f'{self.in_date_format} {self.time_format}'
        else:
            datetime_str = f'{time} {date}'
            datetime_fmt = f'{self.time_format} {self.date_format}'
        return datetime.datetime.strptime(datetime_str, datetime_fmt).isoformat()

    def get_schedule(self, start_date=None, end_date=None, site_id=None, emp_id=None, xml_string="", **tags):
        """
        Wrapper for the GetSchedule method which facilitates adding necessary tags to the default xml string. Pulls schedule for one site for a given date range.

        :param start_date: (str) %Y-%m-%d date string indicating the beginning of the range from which to pull the schedule
        :param end_date: (str) %Y-%m-%d date string indicating the ending of the range from which to pull the schedule
        :param site_id: (str or int) id corresponding to the site that the schedule will be pulled from
        :param xml_string: (xml string)overrides the default credential and/or schedule injection into base_xml
        :param tags: (kwargs) things to be injected into the request.
        :return: xml response string with an error message or a schedule.
        """
        if not start_date and end_date and (site_id or emp_id):
            raise APICallError('kwargs start_date, end_date, and (site_id or emp_id) are all required.')
        xml_string = xml_string if xml_string else self.base_xml
        base_tags = {}
        if site_id:
            base_tags.update({"site_id": site_id})
        if emp_id:
            base_tags.update({"emp_id": str(emp_id)})
        base_tags.update({"start_date": start_date, "end_date": end_date, **tags})
        xml_string = xmlmanip.inject_tags(xml_string, injection_index=2, schedule="")
        xml_string = xmlmanip.inject_tags(xml_string, parent_tag="schedule", **base_tags)
        if self.debug:
            self.last_request = xml_string
        return self.GetSchedule(xml_string)

    def get_schedules(self, start_date=None, end_date=None, site_ids=None, xml_string="", **tags):
        """
        Wrapper for the GetSchedule method which facilitates adding necessary tags to the default xml string.
        Pulls schedule for multiple sites for a given date range. Makes multiple API calls to get schedules from multiple facilities.

        :param start_date: (str) %Y-%m-%d date string indicating the beginning of the range from which to pull the schedule
        :param end_date: (str) %Y-%m-%d date string indicating the ending of the range from which to pull the schedule
        :param site_ids: (list or None) list of ids corresponding to the site(s) that the schedule will be pulled from, defaults to the list pulled from site_file in the __init__ function
        :param xml_string: (xml string) overrides the default credential and/or schedule injection into base_xml
        :param tags: (kwargs) things to be injected into the request.
        :return: xml response string with an error message or a schedule.
        """
        if not site_ids:
            site_ids = self.site_ids
        if not (site_ids and start_date and end_date):
            raise APICallError("Required kwarg site_ids must be an enumerable object of site_id's.")
        xml_string = xml_string if xml_string else self.base_xml
        schedules = []
        for site_id in site_ids:
            schedules.append(self.get_schedule(site_id=site_id, start_date=start_date,
                                               end_date=end_date, xml_string=xml_string))
        return schedules

    def get_schedule_values_list(self, start_date=None, end_date=None, site_ids=None, emp_ids=None, xml_string="", **tags):
        """
        Wrapper for the get_schedules function that returns the retrieved schedules as a list of dicts. This can easily be converted into a DataFrame

        :param start_date: (str) %Y-%m-%d date string indicating the beginning of the range from which to pull the schedule
        :param end_date: (str) %Y-%m-%d date string indicating the ending of the range from which to pull the schedule
        :param site_ids: (list or None) list of ids corresponding to the site(s) that the schedule will be pulled from, defaults to the list pulled from site_file in the __init__ function
        :param emp_ids: (list or None) list of emp_ids corresponding to the employee(s) that the schedule will be pulled for
        :param xml_string: (xml string) overrides the default credential and/or schedule injection into base_xml
        :param tags: (kwargs) things to be injected into the request.
        :return: (OrderedDict) filled with schedules.
        """
        if not site_ids and not hasattr(self, 'site_ids') and not emp_ids:
            raise APICallError("kwarg site_ids or emp_ids is required.")
        elif (site_ids or hasattr(self, 'site_ids')) and emp_ids:
            raise APICallError("schedule queries on both site_ids and emp_ids is currently not supported.")
        elif not site_ids and not emp_ids:
            site_ids = self.site_ids
        id_type = 'site_id' if site_ids else 'emp_id'
        id_list = site_ids if site_ids else emp_ids
        id_list = id_list if issubclass(id_list.__class__, list) else [id_list]
        xml_string = xml_string if xml_string else self.base_xml
        schedule_values_list = []
        for _id in id_list:
            id_kwargs = {id_type: _id}
            schedule_response = self.get_schedule(xml_string=xml_string, start_date=start_date, end_date=end_date,
                                                  **id_kwargs, **tags)
            temp_values_list = xmlmanip.XMLSchema(schedule_response).search('@shiftdate', "", comparison='ne')
            for shifts in temp_values_list:
                schedule_values_list.extend(self._extract_shifts(shifts))
        return schedule_values_list