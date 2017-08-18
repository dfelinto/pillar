"""Authentication code common to the web and api modules."""

import logging
import typing

from flask import session
import flask_login
from werkzeug.local import LocalProxy

from ..api import utils
from ..api.utils import authentication

log = logging.getLogger(__name__)


class UserClass(flask_login.UserMixin):
    def __init__(self, token: typing.Optional[str]):
        # We store the Token instead of ID
        self.id = token
        self.username: str = None
        self.full_name: str = None
        self.objectid: str = None
        self.gravatar: str = None
        self.email: str = None
        self.roles: typing.List[str] = []
        self.groups: typing.List[str] = []

    def has_role(self, *roles):
        """Returns True iff the user has one or more of the given roles."""

        if not self.roles:
            return False

        return bool(set(self.roles).intersection(set(roles)))


class AnonymousUser(flask_login.AnonymousUserMixin, UserClass):
    def __init__(self):
        super().__init__(token=None)

    def has_role(self, *roles):
        return False


def _load_user(token):
    """Loads a user by their token.

    :returns: returns a UserClass instance if logged in, or an AnonymousUser() if not.
    :rtype: UserClass
    """

    db_user = authentication.validate_this_token(token)
    if not db_user:
        return AnonymousUser()

    login_user = UserClass(token)
    login_user.email = db_user['email']
    login_user.objectid = str(db_user['_id'])
    login_user.username = db_user['username']
    login_user.gravatar = utils.gravatar(db_user['email'])
    login_user.roles = db_user.get('roles', [])
    login_user.groups = [str(g) for g in db_user['groups'] or ()]
    login_user.full_name = db_user.get('full_name', '')

    return login_user


def config_login_manager(app):
    """Configures the Flask-Login manager, used for the web endpoints."""

    login_manager = flask_login.LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "users.login"
    login_manager.login_message = ''
    login_manager.anonymous_user = AnonymousUser
    # noinspection PyTypeChecker
    login_manager.user_loader(_load_user)

    return login_manager


def login_user(oauth_token: str, *, load_from_db=False):
    """Log in the user identified by the given token."""

    if load_from_db:
        user = _load_user(oauth_token)
    else:
        user = UserClass(oauth_token)
    flask_login.login_user(user)


def get_blender_id_oauth_token():
    """Returns a tuple (token, ''), for use with flask_oauthlib."""

    from flask import request

    token = session.get('blender_id_oauth_token')
    if token:
        return token

    if request.authorization:
        return request.authorization.username, ''

    return None


def _get_current_web_user() -> UserClass:
    """Returns the current web user as a UserClass instance."""

    return flask_login.current_user


current_web_user: UserClass = LocalProxy(_get_current_web_user)
"""The current web user."""
