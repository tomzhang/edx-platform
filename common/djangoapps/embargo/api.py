"""
The Python API layer of the country access settings. Essentially the middle tier of the project, responsible for all
business logic that is not directly tied to the data itself.

This API is exposed via the middleware(emabargo/middileware.py) layer but may be used directly in-process.

"""

from functools import partial
import logging
import pygeoip

from django.core.cache import cache
from django.conf import settings
from django.http import HttpResponseRedirect, HttpResponseForbidden

from student.models import unique_id_for_user
from embargo.models import CountryAccessRule, IPFilter, RestrictedCourse

log = logging.getLogger(__name__)

# Reasons a user might be blocked.
# These are used to generate info messages in the logs.
REASONS = {
    "ip_blacklist": u"Restricting IP address {ip_addr} {from_course} because IP is blacklisted.",
    "ip_country": u"Restricting IP address {ip_addr} {from_course} because IP is from country {ip_country}.",
    "profile_country": (
        u"Restricting user {user_id} {from_course} because "
        u"the user set the profile country to {profile_country}."
    )
}

WHITE_LIST = "whitelist"
BLACK_LIST = "blacklist"


def _from_course_msg(course_id, course_is_embargoed):
    """
    Format a message indicating whether the user was blocked from a specific course.
    This can be used in info messages, but should not be used in user-facing messages.

    Args:
        course_id (unicode): The ID of the course being accessed.
        course_is_embarged (boolean): Whether the course being accessed is embargoed.

    Returns:
        unicode

    """
    return (
        u"from course {course_id}".format(course_id=course_id)
        if course_is_embargoed
        else u""
    )


def _log_embargo_reason(check_func, course_id, course_is_embargoed):
    """
    Decorator for embargo check functions that will:
        * execute the check function
        * check whether the user is blocked by an embargo, and if so, log the reason
        * return a boolean indicating whether the user was blocked.

    Args:
        check_func (partial): A function that should return unicode reason if the user
            was blocked, otherwise should return None.  This function will be passed
            `course_id` and `course_is_embarged` kwargs so it can format a detailed
            reason message.

        course_id (unicode): The ID of the course the user is trying to access.

        course_is_embargoed (boolean): Whether the course the user is trying
            to access is under an embargo.

    Returns:
        boolean: True iff the user was blocked by an embargo

    """

    def _inner():
        # Perform the check and retrieve the reason string.
        # The reason will be `None` if the user passes the check and can access the course.
        # We pass in the course ID and whether the course is embargoed
        # so that the check function can fill in the "reason" message with more specific details.
        reason = check_func(
            course_id=course_id,
            course_is_embargoed=course_is_embargoed
        )

        # If the reason was `None`, indicate that the user was not blocked.
        if reason is None:
            return False

        # Otherwise, log the reason the user was blocked
        # and return True.
        else:
            msg = u"Embargo: {reason}".format(reason=reason)
            log.info(msg)
            return True

    return _inner


def _embargo_redirect_response():
    """
    The HTTP response to send when the user is blocked from a course.
    This will either be a redirect to a URL configured in Django settings
    or a forbidden response.

    Returns:
        HTTPResponse

    """
    redirect_url = getattr(settings, 'EMBARGO_SITE_REDIRECT_URL', None)
    response = (
        HttpResponseRedirect(redirect_url)
        if redirect_url
        else HttpResponseForbidden('Access Denied')
    )

    return response


def _is_embargoed_by_ip(ip_addr, course_id=u"", course_is_embargoed=False):
    """
    Check whether the user is embargoed based on the IP address.

    Args:
        ip_addr (str): The IP address the request originated from.

    Keyword Args:
        course_id (unicode): The course the user is trying to access.
        course_is_embargoed (boolean): Whether the course the user is accessing has been embargoed.

    Returns:
        A unicode message if the user is embargoed, otherwise `None`

    """
    # If blacklisted, immediately fail
    if ip_addr in IPFilter.current().blacklist_ips:
        return REASONS['ip_blacklist'].format(
            ip_addr=ip_addr,
            from_course=_from_course_msg(course_id, course_is_embargoed)
        )

    # If we're white-listed, then allow access
    if ip_addr in IPFilter.current().whitelist_ips:
        return None

    # Retrieve the country code from the IP address
    # and check it against the list of embargoed countries
    ip_country = _country_code_from_ip(ip_addr)

    if course_id and not CountryAccessRule.is_course_embargoed_in_country_list(course_id, ip_country, "whitelist"):
        return REASONS['ip_country'].format(
            ip_addr=ip_addr,
            ip_country=ip_country,
            from_course=_from_course_msg(course_id, course_is_embargoed)
        )

    if course_id and CountryAccessRule.is_course_embargoed_in_country_list(course_id, ip_country, "blacklist"):
        return REASONS['ip_country'].format(
            ip_addr=ip_addr,
            ip_country=ip_country,
            from_course=_from_course_msg(course_id, course_is_embargoed)
        )

def _is_embargoed_by_profile_country(user, course_id="", course_is_embargoed=False):
    """
    Check whether the user is embargoed based on the country code in the user's profile.

    Args:
        user (User): The user attempting to access courseware.

    Keyword Args:
        course_id (unicode): The course the user is trying to access.
        course_is_embargoed (boolean): Whether the course the user is accessing has been embargoed.

    Returns:
        A unicode message if the user is embargoed, otherwise `None`

    """
    cache_key = u'user.{user_id}.profile.country'.format(user_id=user.id)
    profile_country = cache.get(cache_key)
    if profile_country is None:
        profile = getattr(user, 'profile', None)
        if profile is not None and profile.country.code is not None:
            profile_country = profile.country.code.upper()
        else:
            profile_country = ""
        cache.set(cache_key, profile_country)

    if course_id and not CountryAccessRule.is_course_embargoed_in_country_list(course_id, profile_country, "whitelist"):
        return REASONS['profile_country'].format(
            user_id=unique_id_for_user(user),
            profile_country=profile_country,
            from_course=_from_course_msg(course_id, course_is_embargoed)
        )
    if course_id and CountryAccessRule.is_course_embargoed_in_country_list(course_id, profile_country, "blacklist"):
        return REASONS['profile_country'].format(
            user_id=unique_id_for_user(user),
            profile_country=profile_country,
            from_course=_from_course_msg(course_id, course_is_embargoed)
        )


def _country_code_from_ip(ip_addr):
    """
    Return the country code associated with an IP address.
    Handles both IPv4 and IPv6 addresses.

    Args:
        ip_addr (str): The IP address to look up.

    Returns:
        str: A 2-letter country code.

    """
    if ip_addr.find(':') >= 0:
        return pygeoip.GeoIP(settings.GEOIPV6_PATH).country_code_by_addr(ip_addr)
    else:
        return pygeoip.GeoIP(settings.GEOIP_PATH).country_code_by_addr(ip_addr)


def check_access(user, ip_address, course_key):
    """
    Check is the user with this ip_address has access to the given course

    Params:
        user (User): Currently logged in user object
        ip_address (str): The ip_address of user
        course_key (CourseLocator): CourseLocator object the user is trying to access

    Returns:
        Redirect to a URL configured in Django settings or a forbidden response if any constraints fails or None

    """
    course_is_restricted = RestrictedCourse.is_restricted_course(course_key)
    # If they're trying to access a course that cares about embargoes
    if course_is_restricted:

        # Construct the list of functions that check whether the user is embargoed.
        # We wrap each of these functions in a decorator that logs the reason the user
        # was blocked.
        # Each function should return `True` iff the user is blocked by an embargo.
        check_functions = [
            _log_embargo_reason(check_func, course_key, course_is_restricted)
            for check_func in [
                partial(_is_embargoed_by_ip, ip_address, course_id=course_key),
                partial(_is_embargoed_by_profile_country, user, course_id=course_key)
            ]
        ]

        # Perform each of the checks
        # If the user fails any of the checks, immediately redirect them
        # and skip later checks.
        for check_func in check_functions:
            if check_func():
                return _embargo_redirect_response()

                # If all the check functions pass, implicitly return None
                # so that the middleware processor can continue processing
                # the response.
