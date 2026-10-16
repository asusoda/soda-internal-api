"""Notion dates in the format Google Calendar takes."""

from datetime import datetime, timedelta

import pytz
from sentry_sdk import capture_exception

from core.config import config
from core.log import get_logger

logger = get_logger(__name__)


class DateParser:
    """Parse Notion dates and fill in a missing end."""

    @staticmethod
    def parse_notion_date(date_str: str | None, time_zone: str | None = None) -> dict | None:
        """{"date": ...} for a YYYY-MM-DD string, {"dateTime": ..., "timeZone": ...} for ISO 8601, else None.

        A time with no offset is in time_zone, the time zone of the Notion date, else in config.TIMEZONE.
        A time zone with no IANA name and a non-zero offset gets config.TIMEZONE.
        """
        if not date_str:
            return None

        cleaned_date_str = date_str.strip().rstrip(",")

        try:
            datetime.strptime(cleaned_date_str, "%Y-%m-%d")
            return {"date": cleaned_date_str}
        except ValueError:
            try:
                dt_obj = datetime.fromisoformat(cleaned_date_str.replace("Z", "+00:00"))

                tz_info = dt_obj.tzinfo
                time_zone_str = None
                if tz_info:
                    time_zone_str = getattr(tz_info, "zone", None)
                    if not time_zone_str:
                        if tz_info.utcoffset(dt_obj) == timedelta(0):
                            time_zone_str = "UTC"
                        else:
                            time_zone_str = config.TIMEZONE

                if not time_zone_str:
                    time_zone_str = time_zone or config.TIMEZONE

                return {
                    "dateTime": dt_obj.isoformat(),
                    "timeZone": time_zone_str,
                }
            except ValueError:
                logger.warning(
                    "Invalid or unsupported date format encountered in Notion date field "
                    f"(cleaned length={len(cleaned_date_str)}, original length={len(date_str) if date_str is not None else 'None'})."
                )
                return None
            except Exception as e_iso:
                logger.error(f"Unexpected error parsing ISO date string: {str(e_iso)}")
                capture_exception(e_iso)
                return None
        except Exception as e_date:
            logger.error(f"Unexpected error parsing date string: {str(e_date)}")
            capture_exception(e_date)
            return None

    @staticmethod
    def exclusive_end(end_date_dict: dict | None) -> dict | None:
        """The day after an all-day end, else end_date_dict.

        A Notion all-day end is the last day; a Google Calendar all-day end is the day after the last day.
        """
        if not end_date_dict or "date" not in end_date_dict:
            return end_date_dict
        last_day = datetime.strptime(end_date_dict["date"], "%Y-%m-%d")
        return {"date": (last_day + timedelta(days=1)).strftime("%Y-%m-%d")}

    @staticmethod
    def ensure_end_date(start_date_dict: dict, end_date_dict: dict | None = None) -> dict:
        """end_date_dict if it has a date, else the day after an all-day start or one hour after a timed start.

        If the end cannot be calculated, the result is a copy of the start.
        """
        if end_date_dict and ("date" in end_date_dict or "dateTime" in end_date_dict):
            return end_date_dict

        logger.debug(f"End date missing or invalid. Calculating based on start: {start_date_dict}")

        if "date" in start_date_dict:
            try:
                start_date_obj = datetime.strptime(start_date_dict["date"], "%Y-%m-%d")
                # Google Calendar takes the day after the last day as the end of an all-day event
                end_date_obj = start_date_obj + timedelta(days=1)
                return {"date": end_date_obj.strftime("%Y-%m-%d")}
            except ValueError as e:
                logger.error(f"Error calculating end date for all-day event starting {start_date_dict['date']}: {e}")
                capture_exception(e)
                return start_date_dict.copy()

        elif "dateTime" in start_date_dict:
            try:
                start_dt_iso = start_date_dict["dateTime"]
                start_tz_str = start_date_dict.get("timeZone", config.TIMEZONE)

                start_dt_aware = datetime.fromisoformat(start_dt_iso.replace("Z", "+00:00"))

                if start_dt_aware.tzinfo is None:
                    try:
                        tz_obj = pytz.timezone(start_tz_str)
                        start_dt_aware = tz_obj.localize(start_dt_aware)
                    except pytz.UnknownTimeZoneError:
                        logger.error("Invalid timezone provided when localizing datetime. Using start as end.")
                        return start_date_dict.copy()
                    except Exception as tz_err:
                        logger.error(f"Error applying provided timezone when localizing datetime: {tz_err}")
                        capture_exception(tz_err)
                        return start_date_dict.copy()

                end_dt_aware = start_dt_aware + timedelta(hours=1)

                return {"dateTime": end_dt_aware.isoformat(), "timeZone": start_tz_str}
            except Exception as e:
                logger.error("Error calculating default end time from start date/time. Using start as end.")
                capture_exception(e)
                return start_date_dict.copy()

        logger.error("Start date object is in an unexpected format. Using start as end.")
        return start_date_dict.copy()
