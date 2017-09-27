import unittest
import moment


class TestImport(unittest.TestCase):
    def test_import(self):
        import tangier_api.api


class TestGetSchedule(unittest.TestCase):
    def test_get_schedule(self):
        from tangier_api.api import ScheduleConnection, TESTING_SITE
        connection = ScheduleConnection()
        today = moment.utcnow().strftime("%Y-%m-%d")
        three_months_ago = moment.utcnow().add(months=-2).strftime("%Y-%m-%d")
        connection.get_schedule(site_id=TESTING_SITE, start_date=three_months_ago, end_date=today)


if __name__ == "__main__":
    unittest.main()


