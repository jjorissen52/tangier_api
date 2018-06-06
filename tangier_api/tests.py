import unittest, sys
import moment, xmlmanip


def generate_empty_list_error_response(test, list_name):
    return f'During "{test}", returned {list_name} had a length of 0 indicating ' \
           f'an issue with the API call'


class TestScheduleConnection(unittest.TestCase):
    def test_get_schedule(self):
        from tangier_api.api import ScheduleConnection, TESTING_SITE
        connection = ScheduleConnection()
        today = moment.utcnow().strftime("%Y-%m-%d")
        three_months_ago = moment.utcnow().add(months=-2).strftime("%Y-%m-%d")
        schedule = xmlmanip.XMLSchema(connection.get_schedule(site_id=TESTING_SITE,
                                                              start_date=three_months_ago,
                                                              end_date=today))
        schedule_list = schedule.search(location__contains='')
        self.assertTrue(len(schedule_list) != 0,
                        generate_empty_list_error_response(sys._getframe().f_code.co_name, 'schedule_list'))

    def test_get_schedules(self):
        from tangier_api.api import ScheduleConnection, TESTING_SITE
        connection = ScheduleConnection()
        today = moment.utcnow().strftime("%Y-%m-%d")
        three_months_ago = moment.utcnow().add(months=-2).strftime("%Y-%m-%d")

        schedules = connection.get_schedules(site_ids=[TESTING_SITE, TESTING_SITE],
                                             start_date=three_months_ago,
                                             end_date=today)
        for schedule in schedules:
            schedule_list = xmlmanip.XMLSchema(schedule).search(date__ne='')
            self.assertTrue(len(schedule_list) != 0,
                            generate_empty_list_error_response(sys._getframe().f_code.co_name, 'schedule_list'))

    def test_get_schedule_values_list(self):
        from tangier_api.api import ScheduleConnection, TESTING_SITE
        connection = ScheduleConnection()
        today = moment.utcnow().strftime("%Y-%m-%d")
        three_months_ago = moment.utcnow().add(months=-2).strftime("%Y-%m-%d")
        schedule_list = connection.get_schedule_values_list(site_ids=[TESTING_SITE, TESTING_SITE],
                                                            start_date=three_months_ago,
                                                            end_date=today)
        self.assertTrue(len(schedule_list) != 0,
                        generate_empty_list_error_response(sys._getframe().f_code.co_name, 'schedule_list'))


class TestProviderConnection(unittest.TestCase):
    """
    These tests all use provider_primary_key rather than emp_id since I only query by emp_id. Please provide
    implementations for emp_id if you need them.
    """
    def test_get_provider_info(self):
        from tangier_api.api import ProviderConnection
        provider = ProviderConnection()
        provider_response = xmlmanip.XMLSchema(provider.get_provider_info(all_providers=True))
        provider_list = provider_response.search(provider_primary_key__contains='')
        self.assertTrue(len(provider_list) != 0,
                        generate_empty_list_error_response(sys._getframe().f_code.co_name, 'provider_list'))

    def test_provider_info_values_list(self):
        from tangier_api.api import ProviderConnection
        provider = ProviderConnection()
        provider_list = provider.provider_info_values_list(all_providers=True)
        self.assertTrue(len(provider_list) != 0,
                        generate_empty_list_error_response(sys._getframe().f_code.co_name, 'provider_list'))


class TestLocationConnection(unittest.TestCase):
    def test_add_show_update_list_delete(self):
        from tangier_api.api import LocationConnection
        lconn = LocationConnection()
        add_response = lconn.add_location(site_id='TEST ID', name='Test Facility', short_name='Test Facility Short')
        get_response = lconn.get_locations_info(site_ids=['TEST ID'])
        update_response = lconn.update_location(site_id='TEST ID', new_site_id='NEW TEST ID', name='Test Facility',
                                                short_name='Test Facility Short')
        list_response = lconn.location_info_values_list(site_ids=['NEW TEST ID'])
        delete_response = lconn.delete_location(site_id='NEW TEST ID')
        self.assertTrue(len(list_response) > 0)


if __name__ == "__main__":
    unittest.main()
