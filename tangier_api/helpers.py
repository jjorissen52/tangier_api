import datetime


def date_ranges(start_date, end_date, date_format='%Y-%m-%d'):
    start_date = datetime.datetime.strptime(start_date, date_format)
    end_date = datetime.datetime.strptime(end_date, date_format)
    ranges = []
    while start_date + datetime.timedelta(weeks=8) < end_date:
        ranges.append((start_date.strftime(date_format), (start_date + datetime.timedelta(weeks=8)).strftime(date_format)))
        start_date = start_date + datetime.timedelta(weeks=8, days=1)
    ranges.append((start_date.strftime(date_format), end_date.strftime(date_format)))
    return ranges