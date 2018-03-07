import re
import configparser, os, datetime, logging
from functools import wraps
import random

from requests import Session

from zeep import Client
from zeep.transports import Transport

import xml.etree.ElementTree as ET
import xmlmanip, pandas, mylittlehelpers, numpy

INTERFACE_CONF_FILE = os.environ.get('INTERFACE_CONF_FILE')
INTERFACE_CONF_FILE = os.path.join(INTERFACE_CONF_FILE) if INTERFACE_CONF_FILE else 'tangier.conf'

config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
config.read(INTERFACE_CONF_FILE)

TANGIER_USERNAME = config.get('tangier', 'username')
TANGIER_PASSWORD = config.get('tangier', 'password')
SCHEDULE_ENDPOINT = config.get('tangier', 'schedule_endpoint')
PROVIDER_ENDPOINT = config.get('tangier', 'provider_endpoint')
LOCATION_ENDPOINT = config.get('tangier', 'location_endpoint')
TESTING_SITE = config.get('tangier', 'testing_site')
TESTING_NPI = config.get('tangier', 'testing_npi')
LOG_DIR = config.get('tangier', 'log_dir')
now = datetime.datetime.now()
LOG_DIR_INSERT = f'{now.strftime("%Y-%m-%d")}-{int(now.timestamp())}'
# SCHEDULE_LOG_FILE = os.path.join(LOG_DIR, LOG_DIR_INSERT, f'schedule_log.txt'.upper())
# DUPE_LOG_FILE = os.path.join(LOG_DIR, LOG_DIR_INSERT, f'duplicates_log.txt'.upper())
# EMPTIES_LOG_FILE = os.path.join(LOG_DIR, LOG_DIR_INSERT, f'empties_log.txt'.upper())
# CONFLICTS_LOG_FILE = os.path.join(LOG_DIR, LOG_DIR_INSERT, f'conflicts_log.txt'.upper())
# INFO_LOG_FILE = os.path.join(LOG_DIR, LOG_DIR_INSERT, f'info_log.txt'.upper())

class APICallError(BaseException):
    pass

class APIError(BaseException):
    pass

# schedule_logger = mylittlehelpers.setup_logger('schedule_logger', SCHEDULE_LOG_FILE)
# duplicates_logger = mylittlehelpers.setup_logger('duplicates_logger', DUPE_LOG_FILE)
# empties_logger = mylittlehelpers.setup_logger('empties_logger', EMPTIES_LOG_FILE)
# conflicts_logger = mylittlehelpers.setup_logger('conflicts_logger', CONFLICTS_LOG_FILE)
# info_logger = mylittlehelpers.setup_logger('info_logger', INFO_LOG_FILE)

schedule_logger = logging.getLogger('schedule_logger')
duplicates_logger = logging.getLogger('duplicates_logger')
empties_logger = logging.getLogger('empties_logger')
conflicts_logger = logging.getLogger('conflicts_logger')
info_logger = logging.getLogger('info_logger')


def date_ranges(start_date, end_date, date_format='%Y-%m-%d'):
    start_date = datetime.datetime.strptime(start_date, date_format)
    end_date = datetime.datetime.strptime(end_date, date_format)
    ranges = []
    while start_date + datetime.timedelta(weeks=8) < end_date:
        ranges.append((start_date.strftime(date_format), (start_date + datetime.timedelta(weeks=8)).strftime(date_format)))
        start_date = start_date + datetime.timedelta(weeks=8, days=1)
    ranges.append((start_date.strftime(date_format), end_date.strftime(date_format)))
    return ranges


class ScheduleConnection:
    in_date_format = "%m/%d/%Y"
    datetime_format = "%Y-%m-%dT%H:%M:%S"
    date_format = "%Y-%m-%d"
    time_format = "%I:%M %p"

    def __init__(self, xml_string="", site_file=None, site_id_column_header='site_id', testing=False,
                 endpoint=SCHEDULE_ENDPOINT):
        """
        Initializes the ScheduleConnection. This method attempts to authenticate the connection, pulls site_ids from the site_id file, and determines WSDL definition info

        :param xml_string: override the default xml, which is just <tangier method="schedule.request"/>
        :param site_file: (str) fully qualified path to xlsx or csv document containing all tangier site ids
        :param site_id_column_header: (str) header name of column containing site ids in site_file
        :param endpoint: where the WSDL info is with routing info and SOAP API definitions
        """
        super(self.__class__, self).__init__()
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

        self.base_xml = xmlmanip.inject_tags(self.base_xml, user_name=TANGIER_USERNAME, user_pwd=TANGIER_PASSWORD)
        self.client = Client(endpoint, transport=Transport(session=Session()))
        self.saved_schedule = None

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
            return ScheduleConnection._time_and_date_to_iso(shift_time, shifts_date)

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

    @staticmethod
    def _time_and_date_to_iso(time, date, time_format=time_format, date_format=date_format):
        return datetime.datetime.strptime(f'{time} {date}', f'{time_format} {date_format}').isoformat()

    def get_schedule(self, start_date=None, end_date=None, site_id=None, xml_string="", **tags):
        """
        Wrapper for the GetSchedule method which facilitates adding necessary tags to the default xml string. Pulls schedule for one site for a given date range.

        :param start_date: (str) %Y-%m-%d date string indicating the beginning of the range from which to pull the schedule
        :param end_date: (str) %Y-%m-%d date string indicating the ending of the range from which to pull the schedule
        :param site_id: (str or int) id corresponding to the site that the schedule will be pulled from
        :param xml_string: (xml string)overrides the default credential and/or schedule injection into base_xml
        :param tags: (kwargs) things to be injected into the request.
        :return: xml response string with an error message or a schedule.
        """
        if not start_date and end_date and site_id:
            raise APICallError('kwargs start_date, end_date, and site_id are all required.')
        xml_string = xml_string if xml_string else self.base_xml
        tags = {"site_id": site_id, "start_date": start_date, "end_date": end_date, **tags}
        xml_string = xmlmanip.inject_tags(xml_string, injection_index=2, schedule="")
        xml_string = xmlmanip.inject_tags(xml_string, parent_tag="schedule", **tags)
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

    def get_schedule_values_list(self, start_date=None, end_date=None, site_ids=None, xml_string="", **tags):
        """
        Wrapper for the get_schedules function that returns the retrieved schedules as a list of dicts. This can easily be converted into a DataFrame

        :param start_date: (str) %Y-%m-%d date string indicating the beginning of the range from which to pull the schedule
        :param end_date: (str) %Y-%m-%d date string indicating the ending of the range from which to pull the schedule
        :param site_ids: (list or None) list of ids corresponding to the site(s) that the schedule will be pulled from, defaults to the list pulled from site_file in the __init__ function
        :param xml_string: (xml string) overrides the default credential and/or schedule injection into base_xml
        :param tags: (kwargs) things to be injected into the request.
        :return: (OrderedDict) filled with schedules.
        """
        if not site_ids and not self.site_ids:
            raise APICallError("kwarg site_ids is required.")
        elif not site_ids:
            site_ids = self.site_ids
        elif not issubclass(site_ids.__class__, list):
            site_ids = [site_ids]
        xml_string = xml_string if xml_string else self.base_xml
        schedule_values_list = []

        for site_id in site_ids:
            schedule_response = self.get_schedule(xml_string=xml_string, start_date=start_date, end_date=end_date,
                                                  site_id=site_id, **tags)
            temp_values_list = xmlmanip.XMLSchema(schedule_response).search('@shiftdate', "", comparison='ne')
            for shifts in temp_values_list:
                schedule_values_list.extend(self._extract_shifts(shifts))
        return schedule_values_list

    def save_schedule_from_range(self, start_date=None, end_date=None, site_ids=None, xml_string="", **tags):
        """
        Saves schedule for indicated date range and facilities to ScheduleConnection object

        :param start_date: (str) %Y-%m-%d date string indicating the beginning of the range from which to pull the schedule
        :param end_date: (str) %Y-%m-%d date string indicating the ending of the range from which to pull the schedule
        :param site_ids: (list or None) list of ids corresponding to the site(s) that the schedule will be pulled from, defaults to the list pulled from site_file in the __init__ function
        :param xml_string: (xml string) overrides the default credential and/or schedule injection into base_xml
        :param tags: (kwargs) things to be injected into the request.
        :return:
        """
        schedule_values_list = []
        ranges = date_ranges(start_date, end_date)
        for date_range in ranges:
            print(str(date_range))
            schedule_values_list.extend(
                self.get_schedule_values_list(date_range[0], date_range[1], site_ids, xml_string, **tags))
        df = pandas.DataFrame(schedule_values_list).sort_values(['shift_start_date', 'shift_end_date']).reset_index()
        df = df.drop(['index'], axis=1)
        self.saved_schedule = df.copy()
        schedule_logger.info(self.saved_schedule.to_csv())

    def get_schedule_empties(self, info=False):
        """
        Gets DataFrame of all entries from schedule which were not worked (reportedminutes == 0) in the saved_schedule

        :param info: (bool) whether or not to print out progress
        :return: (DataFrame) of all entries from schedule which were not worked (reportedminutes == 0)
        """
        if self.saved_schedule is None:
            raise APICallError('There must be a saved schedule from save_schedule_from_range.')
        df = self.saved_schedule.copy()
        empties = df[df['reportedminutes'] == '0']
        return empties

    def get_schedule_conflicts(self, info=False):
        """
        Gets DataFrame of all entries where an employee worked a double-booked shift in the saved_schedule

        :param info: (bool) whether or not to print out progress
        :return: (DataFrame) of all entries where an employee worked a double-booked shift
        """
        if self.saved_schedule is None:
            raise APICallError('There must be a saved schedule from save_schedule_from_range.')
        df = self.saved_schedule.copy()
        df = df.sort_values(['shift_start_date', 'shift_end_date'])
        conflict_df = pandas.DataFrame()
        unique_ids = list(df['empid'].dropna().unique())
        for c, emp_id in enumerate(unique_ids):
            if (c % 13 == 12 or c == len(unique_ids) - 1) and info:
                print(f'{(c+1)/len(unique_ids)*100:>5.2f}%')
            elif info:
                print(f'{(c+1)/len(unique_ids)*100:>5.2f}%', end=',  ')
            emp_sched = df.loc[df['empid'] == emp_id]
            for i, row in emp_sched.iterrows():
                for j, row2 in emp_sched.iterrows():
                    if j <= i:
                        continue
                    elif row2['shift_start_date'] > row['shift_end_date']:
                        break
                    if ((row['shift_start_date'] < row2['shift_end_date']) and (
                            row['shift_end_date'] > row2['shift_start_date'])):
                        row['conflict_shift_start_date'], row['conflict_shift_end_date'] = row2['shift_start_date'], \
                                                                                           row2['shift_end_date']
                        row['conflict_index'] = j
                        conflict_df = conflict_df.append(row[['conflict_index', 'empid', 'shift_start_date',
                                                              'shift_end_date', 'conflict_shift_start_date',
                                                              'conflict_shift_end_date']])
        if not conflict_df.empty:
            conflict_df['conflict_index'] = conflict_df['conflict_index'].astype(int)
        return conflict_df

    def get_schedule_duplicates(self, info=False):
        """
        Gets DataFrame of all duplicate entries in the saved_schedule

        :param info: (bool) whether or not to print out progress
        :return: (DataFrame) of all duplicate entries
        """
        if self.saved_schedule is None:
            raise APICallError('There must be a saved schedule from save_schedule_from_range.')
        df = self.saved_schedule.copy()
        dupe_df = pandas.DataFrame()
        unique_ids = list(df['empid'].dropna().unique())
        for c, emp_id in enumerate(unique_ids):
            if (c % 13 == 12 or c == len(unique_ids) - 1) and info:
                print(f'{(c+1)/len(unique_ids)*100:>5.2f}%')
            elif info:
                print(f'{(c+1)/len(unique_ids)*100:>5.2f}%', end=',  ')
            emp_sched = df.loc[df['empid'] == emp_id]
            for i, row in emp_sched.iterrows():
                for j, row2 in emp_sched.iterrows():
                    if j <= i:
                        continue
                    elif row2['shift_start_date'] > row['shift_end_date']:
                        break
                    if ((row['shift_start_date'] == row2['shift_start_date']) and (
                            row['shift_end_date'] == row2['shift_end_date'])):
                        row['dupe_shift_start_date'], row['dupe_shift_end_date'] = row2['shift_start_date'], row2[
                            'shift_end_date']
                        row['dupe_index'] = j
                        dupe_df = dupe_df.append(row[['dupe_index', 'empid', 'shift_start_date', 'shift_end_date',
                                                      'dupe_shift_start_date', 'dupe_shift_end_date']])

        if not dupe_df.empty:
            dupe_df['dupe_index'] = dupe_df['dupe_index'].astype(int)
        return dupe_df

    def generate_duplicates_report(self, dupes):
        dupes = dupes.reset_index()
        # dupes_left will have originals, dupes_right will have duplicates of originals
        dupes_left = self.saved_schedule.loc[dupes['index']].reset_index()
        dupes_right = self.saved_schedule.loc[dupes['dupe_index']].reset_index()
        # we append and sort on the two indices, the final result has alternating rows of orignals and duplicates
        dupes_append = dupes_left.append(dupes_right).reset_index().sort_values(['level_0', 'index'])
        dupes_append = dupes_append.set_index(['level_0'])
        return dupes_append

    def generate_conflicts_report(self, conflicts):
        conflicts = conflicts.reset_index()
        conflicts_left = self.saved_schedule.loc[conflicts['index']].reset_index()
        conflicts_right = self.saved_schedule.loc[conflicts['conflict_index']].reset_index()
        conflicts_append = conflicts_left.append(conflicts_right).reset_index().sort_values(['level_0', 'index'])
        conflicts_append = conflicts_append.set_index(['level_0'])
        return conflicts_append

    def remove_schedule_empties(self):
        """
        Removes all entries from schedule which were not worked (reportedminutes == 0) in the saved_schedule

        :return:
        """
        initial_length = self.saved_schedule.shape[0]
        empty_df = self.get_schedule_empties().reset_index()
        if empty_df.empty:
            print('No empties to remove.')
            empties_logger.info('No empties to remove.')
            return
        rows_to_remove = empty_df.shape[0]
        temp_df = self.saved_schedule.drop(empty_df['index'])
        if temp_df.shape[0] == initial_length - rows_to_remove:
            self.saved_schedule = temp_df
            empties_logger.info(empty_df.to_csv())
        else:
            info_logger.error('ERROR: Empties could not be removed.')
            raise APIError(
                'An unexpected number of entries were removed; this indicates an issue with the saved schedule.')
        print(f'Removed {rows_to_remove} empties.')
        info_logger.info(f'Removed {rows_to_remove} empties.')

    def remove_schedule_duplicates(self):
        """
        Removes all duplicate entries in the saved_schedule

        :return:
        """
        initial_length = self.saved_schedule.shape[0]
        dupe_df = self.get_schedule_duplicates()
        # report must be generated before the duplicates are removed
        duplicates_report = self.generate_duplicates_report(dupe_df)
        if dupe_df.empty:
            print('No duplicates to remove.')
            duplicates_logger.info('No duplicates to remove.')
            return
        rows_to_remove = dupe_df.shape[0]
        temp_df = self.saved_schedule.drop(dupe_df['dupe_index'])
        if temp_df.shape[0] == initial_length - rows_to_remove:
            self.saved_schedule = temp_df
            duplicates_logger.info(duplicates_report.to_csv(index=False))
        else:
            info_logger.error('ERROR: Duplicates could not be removed.')
            raise APIError(
                'An unexpected number of entries were removed; this indicates an issue with the saved schedule.')
        print(f'Removed {rows_to_remove} duplicates.')
        info_logger.info(f'Removed {rows_to_remove} duplicates.')

    def remove_schedule_conflicts(self):
        """
        Removes all conflicting entries in the saved_schedule

        :return:
        """
        initial_length = self.saved_schedule.shape[0]
        conflict_df = self.get_schedule_conflicts()
        # report must be generated before the duplicates are removed
        conflicts_report = self.generate_conflicts_report(conflict_df)
        if conflict_df.empty:
            print('No duplicates to remove.')
            conflicts_logger.info('No conflicts to remove.')
            return
        rows_to_remove = 2 * conflict_df.shape[0]
        temp_df = self.saved_schedule.drop(conflict_df['conflict_index'])
        temp_df = temp_df.drop(conflict_df.reset_index()['index'])
        if temp_df.shape[0] == initial_length - rows_to_remove:
            self.saved_schedule = temp_df
            conflicts_logger.info(conflicts_report.to_csv(index=False))
        else:
            info_logger.error('ERROR: Conflicts could not be removed.')
            raise APIError(
                'An unexpected number of entries were removed; this indicates an issue with the saved schedule.')
        print(f'Removed {rows_to_remove} conflicts.')
        info_logger.info(f'Removed {rows_to_remove} conflicts.')


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
        # sites = {"site_id": site_id for i, site_id in enumerate(site_ids)}
        tags = {f"location__{i}": {"action": "info", "__inner_tag": {"site_id": site_id}} for i, site_id in enumerate(site_ids)}
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
        self.df = self.df.set_index("index" if not original_index_name else original_index_name)
