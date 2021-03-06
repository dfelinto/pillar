import datetime
import hashlib
import urllib.request, urllib.parse, urllib.error
import logging
import traceback
import sys
import typing

import dateutil.parser
from flask import current_app
from flask import request
from flask_login import current_user
from pillarsdk import File
from pillarsdk import Project
from pillarsdk.exceptions import ResourceNotFound
import pillarsdk.utils
from pillar.web import system_util
from pillar.web.utils.exceptions import ConfigError

log = logging.getLogger(__name__)


def get_file(file_id, api=None):
    # TODO: remove this function and just use the Pillar SDK directly.
    if file_id is None:
        return None

    if api is None:
        api = system_util.pillar_api()

    try:
        return File.find(file_id, api=api)
    except ResourceNotFound:
        f = sys.exc_info()[2].tb_frame.f_back
        tb = traceback.format_stack(f=f, limit=2)
        log.warning('File %s not found, but requested from %s\n%s',
                    file_id, request.url, ''.join(tb))
        return None


def attach_project_pictures(project, api):
    """Utility function that queries for file objects referenced in picture
    header and square. In eve we currently can't embed objects in nested
    properties, this is the reason why this exists.
    This function should be moved in the API, attached to a new Project object.
    """

    project.picture_square = get_file(project.picture_square, api=api)
    project.picture_header = get_file(project.picture_header, api=api)


def gravatar(email: str, size=64):
    import warnings
    warnings.warn("the pillar.web.gravatar function is deprecated; use hashlib instead",
                  DeprecationWarning, 2)

    from pillar.api.utils import gravatar as api_gravatar
    return api_gravatar(email, size)


def datetime_now():
    """Returns a datetime.datetime that represents 'now' in UTC."""

    return datetime.datetime.now(tz=pillarsdk.utils.utc)


def pretty_date(time, detail=False, now=None):
    """Get a datetime object or a int() Epoch timestamp and return a
    pretty string like 'an hour ago', 'Yesterday', '3 months ago',
    'just now', etc
    """

    if time is None:
        return None

    # Normalize the 'time' parameter so it's always a datetime.
    if type(time) is int:
        time = datetime.datetime.fromtimestamp(time, tz=pillarsdk.utils.utc)
    elif isinstance(time, str):
        time = dateutil.parser.parse(time)

    now = now or datetime.datetime.now(tz=time.tzinfo)
    diff = now - time  # TODO: flip the sign, so that future = positive and past = negative.

    second_diff = diff.seconds  # Always positive, so -1 second = -1 day + 23h59m59s
    day_diff = diff.days

    if day_diff < 0 and time.year != now.year:
        # "16 Jul 2018"
        pretty = time.strftime("%d %b %Y")

    elif day_diff < -21 and time.year == now.year:
        # "16 Jul"
        pretty = time.strftime("%d %b")

    elif day_diff < -7:
        week_count = -day_diff // 7
        if week_count == 1:
            pretty = "in 1 week"
        else:
            pretty = "in %s weeks" % week_count

    elif day_diff < -1:
        # "next Tuesday"
        pretty = 'next %s' % time.strftime("%A")
    elif day_diff == -1:
        # Compute the actual number of seconds in the future, positively.
        seconds = 24 * 3600 - second_diff
        if seconds < 10:
            return 'just now'
        if seconds < 60:
            return 'in %ss' % seconds
        if seconds < 120:
            return 'in a minute'
        if seconds < 3600:
            return 'in %im' % (seconds // 60)
        if seconds < 7200:
            return 'in an hour'
        if seconds < 86400:
            return 'in %ih' % (seconds // 3600)
    elif day_diff == 0:
        if second_diff < 10:
            return "just now"
        if second_diff < 60:
            return str(second_diff) + "s ago"
        if second_diff < 120:
            return "a minute ago"
        if second_diff < 3600:
            return str(second_diff // 60) + "m ago"
        if second_diff < 7200:
            return "an hour ago"
        if second_diff < 86400:
            return str(second_diff // 3600) + "h ago"

    elif day_diff == 1:
        pretty = "yesterday"

    elif day_diff <= 7:
        # "last Tuesday"
        pretty = 'last %s' % time.strftime("%A")

    elif day_diff <= 22:
        week_count = day_diff // 7
        if week_count == 1:
            pretty = "1 week ago"
        else:
            pretty = "%s weeks ago" % week_count

    elif time.year == now.year:
        # "16 Jul"
        pretty = time.strftime("%d %b")

    else:
        # "16 Jul 2009"
        pretty = time.strftime("%d %b %Y")

    if detail:
        # "Tuesday at 14:20"
        return '%s at %s' % (pretty, time.strftime('%H:%M'))

    return pretty


def current_user_is_authenticated():
    return current_user.is_authenticated


def get_main_project():
    api = system_util.pillar_api()
    try:
        main_project = Project.find(
            current_app.config['MAIN_PROJECT_ID'], api=api)
    except ResourceNotFound:
        raise ConfigError('MAIN_PROJECT_ID was not found. Check config.py.')
    except KeyError:
        raise ConfigError('MAIN_PROJECT_ID missing from config.py')
    return main_project


def is_valid_id(some_id: typing.Union[str, bytes]):
    """Returns True iff the given string is a valid ObjectId.

    Only use this if you do NOT need an ObjectId object. If you do need that,
    use pillar.api.utils.str2id() instead.

    :type some_id: unicode
    :rtype: bool
    """

    if isinstance(some_id, bytes):
        return len(some_id) == 12

    if not isinstance(some_id, str):
        return False

    if len(some_id) != 24:
        return False

    # This is more than 5x faster than checking character by
    # character in a loop.
    try:
        int(some_id, 16)
    except ValueError:
        return False
    return True


def last_page_index(meta_info):
    """Eve pagination; returns the index of the last page.

    :param meta_info: Eve's '_meta' response.
    :returns: Eve page number (base-1) of the last page.
    :rtype: int
    """

    total = meta_info['total']
    if total == 0:
        return 1

    per_page = meta_info['max_results']

    pages = total // per_page
    if total % per_page == 0:
        return pages

    return pages + 1
