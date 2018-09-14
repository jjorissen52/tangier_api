import sys

import pandas
import re
import xmlmanip

from tangier_api.api import ScheduleConnection
from tangier_api.api import ProviderConnection
from tangier_api.api import LocationConnection
from tangier_api import helpers
from tangier_api import exceptions


class ScheduleManipulation(ScheduleConnection):

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
        ranges = helpers.date_ranges(start_date, end_date)
        for date_range in ranges:
            print(str(date_range))
            schedule_values_list.extend(
                self.get_schedule_values_list(date_range[0], date_range[1], site_ids, xml_string, **tags))
        df = pandas.DataFrame(schedule_values_list)
        if df.empty:
            raise exceptions.APICallError('No schedule was returned in the given range.')
        df = df.sort_values(['shift_start_date', 'shift_end_date']).reset_index()
        df = df.drop(['index'], axis=1)
        self.saved_schedule = df.copy()

    def get_schedule_open(self, info=False):
        """
        Gets DataFrame of all entries from schedule where providername == "open" in the saved_schedule

        :param info: (bool) whether or not to print out progress
        :return: (DataFrame) of all entries from schedule which were not worked (reportedminutes == 0)
        """
        if self.saved_schedule is None:
            raise exceptions.APICallError('There must be a saved schedule from save_schedule_from_range.')
        df = self.saved_schedule.copy()
        open_df = df[df['providername'] == 'open']
        return open_df

    def get_schedule_empties(self, info=False):
        """
        Gets DataFrame of all entries from schedule which were not worked (reportedminutes == 0) in the saved_schedule

        :param info: (bool) whether or not to print out progress
        :return: (DataFrame) of all entries from schedule which were not worked (reportedminutes == 0)
        """
        if self.saved_schedule is None:
            raise exceptions.APICallError('There must be a saved schedule from save_schedule_from_range.')
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
            raise exceptions.APICallError('There must be a saved schedule from save_schedule_from_range.')
        df = self.saved_schedule.copy()
        if not 'provider_primary_key' in df.columns:
            raise exceptions.APICallError('get_schedule_conflicts, and get_schedule_duplicates '
                               'rely on use of provider_primary_key=True.')
        df = df.sort_values(['shift_start_date', 'shift_end_date'])
        conflict_df = pandas.DataFrame()
        unique_ids = list(df['provider_primary_key'].dropna().unique())
        for c, emp_id in enumerate(unique_ids):
            if (c % 13 == 12 or c == len(unique_ids) - 1) and info:
                print(f'{(c+1)/len(unique_ids)*100:>5.2f}%')
            elif info:
                print(f'{(c+1)/len(unique_ids)*100:>5.2f}%', end=',  ')
            emp_sched = df.loc[df['provider_primary_key'] == emp_id]
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
                        conflict_df = conflict_df.append(
                            row[['conflict_index', 'provider_primary_key', 'shift_start_date',
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
            raise exceptions.APICallError('There must be a saved schedule from save_schedule_from_range.')
        df = self.saved_schedule.copy()
        if not 'provider_primary_key' in df.columns:
            raise exceptions.APICallError('get_schedule_conflicts, and get_schedule_duplicates '
                               'rely on use of provider_primary_key=True.')
        dupe_df = pandas.DataFrame()
        unique_ids = list(df['provider_primary_key'].dropna().unique())
        for c, emp_id in enumerate(unique_ids):
            if (c % 13 == 12 or c == len(unique_ids) - 1) and info:
                print(f'{(c+1)/len(unique_ids)*100:>5.2f}%')
            elif info:
                print(f'{(c+1)/len(unique_ids)*100:>5.2f}%', end=',  ')
            emp_sched = df.loc[df['provider_primary_key'] == emp_id]
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
                        dupe_df = dupe_df.append(
                            row[['dupe_index', 'provider_primary_key', 'shift_start_date', 'shift_end_date',
                                 'dupe_shift_start_date', 'dupe_shift_end_date']])
        if not dupe_df.empty:
            dupe_df['dupe_index'] = dupe_df['dupe_index'].astype(int)
        return dupe_df

    def generate_duplicates_report(self, dupes):
        dupes = dupes.reset_index()
        # dupes_left will have originals, dupes_right will have duplicates of originals
        if not 'index' in dupes.columns or not 'dupe_index' in dupes.columns:
            return pandas.DataFrame()
        dupes_left = self.saved_schedule.loc[dupes['index']].reset_index()
        dupes_right = self.saved_schedule.loc[dupes['dupe_index']].reset_index()
        # we append and sort on the two indices, the final result has alternating rows of orignals and duplicates
        dupes_append = dupes_left.append(dupes_right).reset_index().sort_values(['level_0', 'index'])
        dupes_append = dupes_append.set_index(['level_0'])
        return dupes_append

    def generate_conflicts_report(self, conflicts):
        conflicts = conflicts.reset_index()
        conflicts_left = self.saved_schedule.loc[conflicts['index']].reset_index()
        if not 'index' in conflicts.columns or not 'conflict_index' in conflicts.columns:
            return pandas.DataFrame()
        conflicts_right = self.saved_schedule.loc[conflicts['conflict_index']].reset_index()
        conflicts_append = conflicts_left.append(conflicts_right).reset_index().sort_values(['level_0', 'index'])
        conflicts_append = conflicts_append.set_index(['level_0'])
        return conflicts_append

    def remove_schedule_open(self):
        """
        Removes all entries from schedule which are just open shifts (providername == 'open') in the saved_schedule

        :return:
        """
        initial_length = self.saved_schedule.shape[0]
        open_df = self.get_schedule_open().reset_index()
        if open_df.empty:
            print('No open shifts to remove.')
            return
        rows_to_remove = open_df.shape[0]
        temp_df = self.saved_schedule.drop(open_df['index'])
        if temp_df.shape[0] == initial_length - rows_to_remove:
            self.saved_schedule = temp_df
        else:
            raise exceptions.APIError(
                'An unexpected number of entries were removed; this indicates an issue with the saved schedule.')
        print(f'Removed {rows_to_remove} open shifts.')

    def remove_schedule_empties(self):
        """
        Removes all entries from schedule which were not worked (reportedminutes == 0) in the saved_schedule

        :return:
        """
        initial_length = self.saved_schedule.shape[0]
        empty_df = self.get_schedule_empties().reset_index()
        if empty_df.empty:
            print('No empties to remove.')
            return
        rows_to_remove = empty_df.shape[0]
        temp_df = self.saved_schedule.drop(empty_df['index'])
        if temp_df.shape[0] == initial_length - rows_to_remove:
            self.saved_schedule = temp_df
        else:
            raise exceptions.APIError(
                'An unexpected number of entries were removed; this indicates an issue with the saved schedule.')
        print(f'Removed {rows_to_remove} empties.')

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
            return
        rows_to_remove = dupe_df.shape[0]
        temp_df = self.saved_schedule.drop(dupe_df['dupe_index'])
        if temp_df.shape[0] == initial_length - rows_to_remove:
            self.saved_schedule = temp_df
        else:
            raise exceptions.APIError(
                'An unexpected number of entries were removed; this indicates an issue with the saved schedule.')
        print(f'Removed {rows_to_remove} duplicates.')

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
            return
        rows_to_remove = 2 * conflict_df.shape[0]
        temp_df = self.saved_schedule.drop(conflict_df['conflict_index'])
        temp_df = temp_df.drop(conflict_df.reset_index()['index'])
        if temp_df.shape[0] == initial_length - rows_to_remove:
            self.saved_schedule = temp_df
        else:
            raise exceptions.APIError(
                'An unexpected number of entries were removed; this indicates an issue with the saved schedule.')
        print(f'Removed {rows_to_remove} conflicts.')


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


class ScheduleWithData:

    def __init__(self, schedule_connection, provider_connection, location_connection):
        try:
            import pandas
        except:
            raise ImportError(f'{self.__name__} requires pandas to be importable in your environment.')
        if not isinstance(schedule_connection, ScheduleConnection):
            raise exceptions.APIError('schedule_connection argument (arg[0]) must be a ScheduleConnection instance.')
        if not isinstance(provider_connection, ProviderConnection):
            raise exceptions.APIError('provider_connection argument (arg[1]) must be a ProviderConnection instance.')
        if not isinstance(location_connection, LocationConnection):
            raise exceptions.APIError('location_connection argument (arg[0]) must be a LocationConnection instance.')
        self.sconn = schedule_connection
        self.pconn = provider_connection
        self.lconn = location_connection

    def _get_provider_info(self):
        self.providers = pandas.DataFrame(self.pconn.provider_info_values_list(all_providers=True,
                                                                               use_primary_keys=True)).fillna('')

    def _get_location_info(self):
        self.locations = pandas.DataFrame(self.lconn.location_info_values_list(site_ids='ALL_SITE_IDS')).fillna('')

    def save_schedule_from_range(self, start_date, end_date):
        self._get_provider_info()
        self._get_location_info()
        self.sconn.save_schedule_from_range(start_date, end_date,
                                            site_ids=list(self.locations['site_id'].unique()),
                                            include_provider_primary_key='true')
        self.saved_schedule = self.sconn.saved_schedule
        self.temp_locations = self.locations.drop(columns=['@action', 'is_scheduled']) \
            .rename(columns={'name': 'site_name', 'short_name': 'site_short_name'})
        self.temp_providers = self.providers.drop(
            columns=['@action', 'processed', 'comment', 'street', 'city', 'state', 'zip'])
        with_sites = self.saved_schedule.merge(self.temp_locations, how='left', left_on=['siteid'],
                                               right_on=['site_id']).drop(columns=['location'])
        with_all = with_sites.merge(self.temp_providers, how='left', left_on=['providerprimarykey'],
                                    right_on=['provider_primary_key'])
        with_all = with_all.drop(columns=['empid', 'siteid', 'providerprimarykey'])
        self.saved_schedule = with_all.fillna('')
        self.sconn.saved_schedule = self.saved_schedule


class ProviderLocations:

    def __init__(self, pconn, lconn):
        self.pconn = pconn
        self.lconn = lconn
        self.all_locations = lconn.location_info_values_list()
        self.all_providers = pconn.provider_info_values_list(all_providers=True)
        self.all_location_provider_values = []

    @property
    def all_location_provider_values(self):
        """
        we want to go get them if an access is attempted and we haven't gotten them already
        """
        if not self.__all_location_provider_values:
            self.all_location_provider_values = self._get_all_location_provider_values()
        return self.__all_location_provider_values

    @all_location_provider_values.setter
    def all_location_provider_values(self, val):
        self.__all_location_provider_values = [*val]

    def _get_all_location_provider_values(self):
        values_list, current_line = [], ''
        for location in self.all_locations:
            values_list.extend(self.location_provider_values(location['site_id']))
            current_line = self._print_stream(location['site_id'], current_line)
        self.all_location_provider_values = [*values_list]
        return values_list

    def _print_stream(self, current_item, current_line):
        new_line = f'{current_line + " " if current_line else ""}{current_item}'
        if len(new_line) > 79:
            new_line = f'{current_item} '
            sys.stdout.write('\n')
            sys.stdout.write(new_line)
        else:
            sys.stdout.write(f'{current_item} ')
        sys.stdout.flush()
        return new_line

    def location_provider_info(self, site_id):
        """
        Sends a provider info request info for all provider_ids for one site_id
        :param site_id_in: (str) site_id to get provider info for
        :return: xml with a provider info response
        """
        xml_string = self.pconn.base_xml
        xml_string = xmlmanip.inject_tags(xml_string, injection_index=2, providers="")
        provider_dict = {
            'provider': {
                "action": "info", "__inner_tag": {
                    "site_id": site_id,
                    "provider_primary_key": "ALL",
                }
            }
        }
        xml_string = xmlmanip.inject_tags(xml_string, parent_tag="providers", **provider_dict)
        return self.pconn.MaintainProviders(xml_string).encode('utf-8')

    def location_provider_values(self, site_id):
        location_provider_info_response = self.location_provider_info(site_id)
        location_provider_info_schema = xmlmanip.XMLSchema(location_provider_info_response)
        location_provider_values = location_provider_info_schema.search(site_id__ne='')
        return location_provider_values

    def join_all_locations_with_all_providers(self):
        normalized_provider_location_values = self.all_location_provider_values
        normalized_provider_location_values_df = pandas.DataFrame(normalized_provider_location_values)
        provider_info_df = pandas.DataFrame(self.all_providers)
        joined_df = normalized_provider_location_values_df.merge(provider_info_df, how='inner',
                                                                 left_on=['provider_primary_key', 'emp_id'],
                                                                 right_on=['provider_primary_key', 'emp_id'])
        return joined_df
