import typing

import bson
import responses

from pillar.tests import AbstractPillarTest
from pillar.api.utils import remove_private_keys


class OrganizationCruTest(AbstractPillarTest):
    """Test creating and updating organizations."""

    def test_create_org(self):
        self.enter_app_context()

        # There should be no organizations to begin with.
        db = self.app.db('organizations')
        self.assertEqual(0, db.count())

        admin_uid = self.create_user(24 * 'a')
        org_doc = self.app.org_manager.create_new_org('Хакеры', admin_uid, 25)

        self.assertIsNotNone(db.find_one(org_doc['_id']))
        self.assertEqual(bson.ObjectId(24 * 'a'), org_doc['admin_uid'])
        self.assertEqual('Хакеры', org_doc['name'])
        self.assertEqual(25, org_doc['seat_count'])

    def test_assign_users(self):
        self.enter_app_context()

        admin_uid = self.create_user(24 * 'a')
        member1_uid = self.create_user(24 * 'b', email='member1@example.com')

        om = self.app.org_manager
        org_doc = om.create_new_org('Хакеры', admin_uid, 25)

        new_org_doc = om.assign_users(
            org_doc['_id'],
            ['member1@example.com', 'member2@example.com'])

        db = self.app.db('organizations')
        db_org = db.find_one(org_doc['_id'])

        self.assertEqual([member1_uid], db_org['members'])
        self.assertEqual(['member2@example.com'], db_org['unknown_members'])

        self.assertEqual([member1_uid], new_org_doc['members'])
        self.assertEqual(['member2@example.com'], new_org_doc['unknown_members'])

    def test_remove_users(self):
        self.enter_app_context()
        om = self.app.org_manager

        admin_uid = self.create_user(24 * 'a')
        self.create_user(24 * 'b', email='member1@example.com')
        org_doc = om.create_new_org('Хакеры', admin_uid, 25)

        om.assign_users(
            org_doc['_id'],
            ['member1@example.com', 'member2@example.com'])

        new_org_doc = None  # to prevent 'might not be assigned' warning later on.
        for email in ('member1@example.com', 'member2@example.com'):
            new_org_doc = om.remove_user(org_doc['_id'], email=email)

        db = self.app.db('organizations')
        db_org = db.find_one(org_doc['_id'])

        self.assertEqual([], db_org['members'])
        self.assertEqual([], db_org['unknown_members'])

        self.assertEqual([], new_org_doc['members'])
        self.assertEqual([], new_org_doc['unknown_members'])

    def test_assign_user_roles(self):
        self.enter_app_context()

        admin_uid = self.create_user(24 * 'a')
        member1_uid = self.create_user(24 * 'b',
                                       email='member1@example.com',
                                       roles={'subscriber', 'monkeyhead'})
        om = self.app.org_manager
        org_doc = om.create_new_org('Хакеры', admin_uid, 25,
                                    org_roles=['org-xакеры'])

        new_org_doc = om.assign_users(org_doc['_id'], ['member1@example.com'])
        self.assertEqual(['org-xакеры'], new_org_doc['org_roles'])

        users_coll = self.app.db('users')

        member1_doc = users_coll.find_one(member1_uid)
        self.assertEqual(set(member1_doc['roles']), {'subscriber', 'monkeyhead', 'org-xакеры'})

    def test_revoke_user_roles_simple(self):
        self.enter_app_context()

        admin_uid = self.create_user(24 * 'a')
        member1_uid = self.create_user(24 * 'b',
                                       email='member1@example.com',
                                       roles={'subscriber', 'monkeyhead'})
        om = self.app.org_manager
        org_doc = om.create_new_org('Хакеры', admin_uid, 25, org_roles=['org-xакеры'])

        om.assign_users(org_doc['_id'], ['member1@example.com'])
        om.remove_user(org_doc['_id'], email='member1@example.com')

        users_coll = self.app.db('users')

        member1_doc = users_coll.find_one(member1_uid)
        self.assertEqual(set(member1_doc['roles']), {'subscriber', 'monkeyhead'})

    def test_revoke_user_roles_multiorg_by_email(self):
        self.enter_app_context()

        admin_uid = self.create_user(24 * 'a')
        member1_uid = self.create_user(24 * 'b',
                                       email='member1@example.com',
                                       roles={'subscriber', 'monkeyhead'})
        om = self.app.org_manager
        org1 = om.create_new_org('Хакеры', admin_uid, 25, org_roles=['org-xакеры', 'org-subs'])
        org2 = om.create_new_org('अजिङ्गर', admin_uid, 25, org_roles=['org-अजिङ्गर', 'org-subs'])

        om.assign_users(org1['_id'], ['member1@example.com'])
        om.assign_users(org2['_id'], ['member1@example.com'])
        om.remove_user(org1['_id'], email='member1@example.com')

        users_coll = self.app.db('users')

        member1_doc = users_coll.find_one(member1_uid)
        self.assertEqual(set(member1_doc['roles']),
                         {'subscriber', 'monkeyhead', 'org-subs', 'org-अजिङ्गर'})

    def test_revoke_user_roles_multiorg_by_user_id(self):
        self.enter_app_context()

        admin_uid = self.create_user(24 * 'a')
        member1_uid = self.create_user(24 * 'b',
                                       email='member1@example.com',
                                       roles={'subscriber', 'monkeyhead'})
        om = self.app.org_manager
        org1 = om.create_new_org('Хакеры', admin_uid, 25, org_roles=['org-xакеры', 'org-subs'])
        org2 = om.create_new_org('अजिङ्गर', admin_uid, 25, org_roles=['org-अजिङ्गर', 'org-subs'])

        # Hack the DB to add the member as "unknown member" too, even though we know this user.
        # This has to be handled cleanly by the removal too.
        orgs_coll = self.app.db('organizations')
        orgs_coll.update_one({'_id': org1['_id']},
                             {'$set': {'unknown_members': ['member1@example.com']}})

        om.assign_users(org1['_id'], ['member1@example.com'])
        om.assign_users(org2['_id'], ['member1@example.com'])
        om.remove_user(org1['_id'], user_id=member1_uid)

        users_coll = self.app.db('users')

        member1_doc = users_coll.find_one(member1_uid)
        self.assertEqual(set(member1_doc['roles']),
                         {'subscriber', 'monkeyhead', 'org-subs', 'org-अजिङ्गर'})

        # The unknown members list should be empty.
        db_org1 = orgs_coll.find_one(org1['_id'])
        self.assertEqual(db_org1['unknown_members'], [])


class OrganizationPatchTest(AbstractPillarTest):
    """Test PATCHing organizations."""

    def test_assign_users(self):
        self.enter_app_context()

        admin_uid = self.create_user(24 * 'a', token='admin-token')
        member1_uid = self.create_user(24 * 'b', email='member1@example.com')

        om = self.app.org_manager
        org_doc = om.create_new_org('Хакеры', admin_uid, 25)
        org_id = org_doc['_id']

        # Try the PATCH
        resp = self.patch(f'/api/organizations/{org_id}',
                          json={
                              'op': 'assign-users',
                              'emails': ['member1@example.com', 'member2@example.com'],
                          },
                          auth_token='admin-token')
        new_org_doc = resp.get_json()

        db = self.app.db('organizations')
        db_org = db.find_one(org_id)

        self.assertEqual([member1_uid], db_org['members'])
        self.assertEqual(['member2@example.com'], db_org['unknown_members'])

        self.assertEqual([str(member1_uid)], new_org_doc['members'])
        self.assertEqual(['member2@example.com'], new_org_doc['unknown_members'])

    def test_assign_single_user(self):
        self.enter_app_context()

        admin_uid = self.create_user(24 * 'a', token='admin-token')
        member1_uid = self.create_user(24 * 'b', email='member1@example.com')

        om = self.app.org_manager
        org_doc = om.create_new_org('Хакеры', admin_uid, 25)
        org_id = org_doc['_id']

        self.assertFalse(om.user_has_organizations(member1_uid))

        # Try the PATCH
        resp = self.patch(f'/api/organizations/{org_id}',
                          json={
                              'op': 'assign-user',
                              'user_id': str(member1_uid),
                          },
                          auth_token='admin-token')
        new_org_doc = resp.get_json()

        db = self.app.db('organizations')
        db_org = db.find_one(org_id)

        self.assertEqual([member1_uid], db_org['members'])
        self.assertEqual([str(member1_uid)], new_org_doc['members'])

        # The user should now have an organization
        self.assertTrue(om.user_has_organizations(member1_uid))

    def test_assign_users_access_denied(self):
        self.enter_app_context()

        admin_uid = self.create_user(24 * 'a', token='admin-token')
        self.create_user(24 * 'b', email='member1@example.com', token='monkey-token')

        om = self.app.org_manager
        org_doc = om.create_new_org('Хакеры', admin_uid, 25)
        org_id = org_doc['_id']

        # Try the PATCH
        self.patch(f'/api/organizations/{org_id}',
                   json={
                       'op': 'assign-users',
                       'emails': ['member1@example.com', 'member2@example.com'],
                   },
                   auth_token='monkey-token',
                   expected_status=403)

        db = self.app.db('organizations')
        db_org = db.find_one(org_id)

        self.assertEqual([], db_org['members'])
        self.assertEqual([], db_org['unknown_members'])

    def test_remove_user_by_email(self):
        self.enter_app_context()
        om = self.app.org_manager

        admin_uid = self.create_user(24 * 'a', token='admin-token')
        self.create_user(24 * 'b', email='member1@example.com')
        org_doc = om.create_new_org('Хакеры', admin_uid, 25)
        org_id = org_doc['_id']

        om.assign_users(org_id, ['member1@example.com', 'member2@example.com'])

        # Try the PATCH to remove a known user
        resp = self.patch(f'/api/organizations/{org_id}',
                          json={
                              'op': 'remove-user',
                              'email': 'member1@example.com',
                          },
                          auth_token='admin-token')
        new_org_doc = resp.get_json()

        db = self.app.db('organizations')
        db_org = db.find_one(org_id)

        self.assertEqual([], db_org['members'])
        self.assertEqual(['member2@example.com'], db_org['unknown_members'])

        self.assertEqual([], new_org_doc['members'])
        self.assertEqual(['member2@example.com'], new_org_doc['unknown_members'])

        # Try the PATCH to remove an unknown user
        resp = self.patch(f'/api/organizations/{org_id}',
                          json={
                              'op': 'remove-user',
                              'email': 'member2@example.com',
                          },
                          auth_token='admin-token')
        new_org_doc = resp.get_json()

        db_org = db.find_one(org_id)

        self.assertEqual([], db_org['members'])
        self.assertEqual([], db_org['unknown_members'])

        self.assertEqual([], new_org_doc['members'])
        self.assertEqual([], new_org_doc['unknown_members'])

    def test_remove_user_by_id(self):
        self.enter_app_context()
        om = self.app.org_manager

        admin_uid = self.create_user(24 * 'a', token='admin-token')
        member_uid = self.create_user(24 * 'b', email='member1@example.com')
        org_doc = om.create_new_org('Хакеры', admin_uid, 25)
        org_id = org_doc['_id']

        om.assign_users(org_id, ['member1@example.com', 'member2@example.com'])
        self.assertTrue(om.user_has_organizations(member_uid))

        # Try the PATCH to remove a known user
        resp = self.patch(f'/api/organizations/{org_id}',
                          json={
                              'op': 'remove-user',
                              'user_id': str(member_uid),
                          },
                          auth_token='admin-token')
        new_org_doc = resp.get_json()

        db = self.app.db('organizations')
        db_org = db.find_one(org_id)

        self.assertEqual([], db_org['members'])
        self.assertEqual(['member2@example.com'], db_org['unknown_members'])

        self.assertEqual([], new_org_doc['members'])
        self.assertEqual(['member2@example.com'], new_org_doc['unknown_members'])

        self.assertFalse(om.user_has_organizations(member_uid))

        # Try the PATCH to remove an unknown user
        resp = self.patch(f'/api/organizations/{org_id}',
                          json={
                              'op': 'remove-user',
                              'user_id': 24 * 'f',
                          },
                          auth_token='admin-token',
                          expected_status=422)

        db_org = db.find_one(org_id)
        self.assertEqual([], db_org['members'])
        self.assertEqual(['member2@example.com'], db_org['unknown_members'])

    def test_remove_self(self):
        self.enter_app_context()
        om = self.app.org_manager

        admin_uid = self.create_user(24 * 'a', token='admin-token')
        member_uid = self.create_user(24 * 'b', email='member1@example.com', token='member-token')
        org_doc = om.create_new_org('Хакеры', admin_uid, 25)
        org_id = org_doc['_id']

        om.assign_users(org_id, ['member1@example.com'])

        # Try the PATCH to remove self.
        resp = self.patch(f'/api/organizations/{org_id}',
                          json={
                              'op': 'remove-user',
                              'user_id': str(member_uid),
                          },
                          auth_token='member-token')
        new_org_doc = resp.get_json()

        db = self.app.db('organizations')
        db_org = db.find_one(org_id)

        self.assertEqual([], db_org['members'])
        self.assertEqual([], new_org_doc['members'])

    def test_edit_from_web(self):
        self.enter_app_context()
        om = self.app.org_manager

        admin_uid = self.create_user(24 * 'a', token='admin-token')
        org_doc = om.create_new_org('Хакеры', admin_uid, 25)
        org_id = org_doc['_id']

        # Try the PATCH to remove a known user
        self.patch(f'/api/organizations/{org_id}',
                   json={
                       'op': 'edit-from-web',
                       'name': '  Blender Institute ',
                       'description': '\nOpen Source animation studio ',
                       'website': '   https://blender.institute/  ',
                   },
                   auth_token='admin-token',
                   expected_status=204)

        db = self.app.db('organizations')
        db_org = db.find_one(org_id)

        self.assertEqual('Blender Institute', db_org['name'])
        self.assertEqual('Open Source animation studio', db_org['description'])
        self.assertEqual('https://blender.institute/', db_org['website'])

    def test_change_roles(self):
        self.enter_app_context()
        om = self.app.org_manager

        self.create_user(24 * '1', roles={'admin'}, token='uberadmin')

        admin_uid = self.create_user(24 * 'a', token='admin-token')
        org_doc = om.create_new_org('Хакеры', admin_uid, 25, org_roles={'org-subscriber'})
        org_id = org_doc['_id']

        # First assign the user, then change the organization's roles.
        # This should refresh the roles on all its members.
        member1_uid = self.create_user(24 * 'b', email='member1@example.com', roles={'betatester'})
        om.assign_single_user(org_id, user_id=member1_uid)

        # Try the PATCH to change the roles
        self.patch(f'/api/organizations/{org_id}',
                   json={
                       'op': 'edit-from-web',
                       'name': '  Blender Institute ',
                       'description': '\nOpen Source animation studio ',
                       'website': '   https://blender.institute/  ',
                       'org_roles': ['org-subscriber', 'org-flamenco'],
                   },
                   auth_token='uberadmin',
                   expected_status=204)

        db_user = self.fetch_user_from_db(member1_uid)
        self.assertEqual({'betatester', 'org-subscriber', 'org-flamenco'}, set(db_user['roles']))

    def test_assign_admin(self):
        self.enter_app_context()
        om = self.app.org_manager

        admin_uid = self.create_user(24 * 'a', token='admin-token')
        new_admin_uid = self.create_user(24 * 'b', token='other-admin-token')

        org_doc = om.create_new_org('Хакеры', admin_uid, 25)
        org_id = org_doc['_id']

        # Try the PATCH to assign the other user as admin
        self.patch(f'/api/organizations/{org_id}',
                   json={
                       'op': 'assign-admin',
                       'user_id': str(new_admin_uid),
                   },
                   auth_token='admin-token',
                   expected_status=204)

        db = self.app.db('organizations')
        db_org = db.find_one(org_id)

        self.assertEqual(new_admin_uid, db_org['admin_uid'])

    def test_assign_admin_as_nonadmin(self):
        self.enter_app_context()
        om = self.app.org_manager

        admin_uid = self.create_user(24 * 'a', token='admin-token')
        new_admin_uid = self.create_user(24 * 'b', token='other-admin-token')

        org_doc = om.create_new_org('Хакеры', admin_uid, 25)
        org_id = org_doc['_id']

        # Try the PATCH to assign the other user as admin
        self.patch(f'/api/organizations/{org_id}',
                   json={
                       'op': 'assign-admin',
                       'user_id': str(new_admin_uid),
                   },
                   auth_token='other-admin-token',
                   expected_status=403)

        db = self.app.db('organizations')
        db_org = db.find_one(org_id)

        self.assertEqual(admin_uid, db_org['admin_uid'])


class OrganizationResourceEveTest(AbstractPillarTest):
    """Test GET/POST/PUT access to Organization resource"""

    def setUp(self, **kwargs):
        super().setUp(**kwargs)

        self.enter_app_context()
        self.om = self.app.org_manager

        # Pillar admin
        self.create_user(24 * '1', roles={'admin'}, token='uberadmin')

        # Create organizations with admin who is not organization member.
        self.admin1_uid = self.create_user(24 * 'a', token='admin1-token')
        self.admin2_uid = self.create_user(24 * 'b', token='admin2-token')

        org_doc = self.om.create_new_org('Хакеры 1', self.admin1_uid, 25)
        self.org1_id = org_doc['_id']
        org_doc = self.om.create_new_org('Хакеры 2', self.admin2_uid, 10)
        self.org2_id = org_doc['_id']

        # Create members of the organizations.
        self.member1_uid = self.create_user(24 * 'd',
                                            email='member1@example.com',
                                            token='member1-token')
        self.member2_uid = self.create_user(24 * 'e',
                                            email='member2@example.com',
                                            token='member2-token')
        self.om.assign_users(self.org1_id, ['member1@example.com', 'member2@example.com'])
        self.om.assign_users(self.org2_id, ['member2@example.com'])

        # Create an outside user.
        self.outsider_uid = self.create_user(24 * '0', token='outsider-token')

        # Re-fetch the organizations so that self.org_docx has the correct etag.
        self.org1_doc = self._from_db(self.org1_id)
        self.org2_doc = self._from_db(self.org2_id)

    def _from_db(self, org_id) -> dict:
        return self.om._get_org(org_id)

    def test_list_as_pillar_admin(self):
        """Pillar Admins should see all orgs"""

        resp = self.get('/api/organizations', auth_token='uberadmin')
        docs = resp.get_json()

        self.assertEqual(2, docs['_meta']['total'])
        self.assertEqual({str(self.org1_id), str(self.org2_id)},
                         {doc['_id'] for doc in docs['_items']})

    def test_list_as_admin1(self):
        """Admins should only see their own orgs"""

        resp = self.get('/api/organizations', auth_token='admin1-token')
        docs = resp.get_json()

        self.assertEqual(1, docs['_meta']['total'])
        self.assertEqual(str(self.org1_id), docs['_items'][0]['_id'])

    def test_list_as_member(self):
        """Members should only see their own orgs"""

        resp = self.get('/api/organizations', auth_token='member1-token')
        docs = resp.get_json()

        self.assertEqual(1, docs['_meta']['total'])
        self.assertEqual(str(self.org1_id), docs['_items'][0]['_id'])

        resp = self.get('/api/organizations', auth_token='member2-token')
        docs = resp.get_json()

        self.assertEqual(2, docs['_meta']['total'])
        self.assertEqual({str(self.org1_id), str(self.org2_id)},
                         {doc['_id'] for doc in docs['_items']})

    def test_list_as_outsider(self):
        """Outsiders shouldn't see any orgs"""

        resp = self.get('/api/organizations', auth_token='outsider-token')
        docs = resp.get_json()

        self.assertEqual(0, docs['_meta']['total'])
        self.assertEqual([], docs['_items'])

    def test_list_as_anonymous(self):
        """Anonymous users should be denied"""

        self.get('/api/organizations', expected_status=403)

    def test_create_as_pillar_admin(self):
        """Pillar admins should be able to create a new organization"""

        new_org = {
            'name': 'Union of €-forgers',
            'seat_count': 5,
            'admin_uid': self.admin1_uid,
        }
        resp = self.post('/api/organizations', auth_token='uberadmin', json=new_org,
                         expected_status=201)
        new_doc = resp.get_json()

        org_id = bson.ObjectId(new_doc['_id'])
        db_org = self._from_db(org_id)
        self.assertEqual(new_org['name'], db_org['name'])
        self.assertEqual(self.admin1_uid, db_org['admin_uid'])

    def _create_test(self, auth_token):
        """Generic creation test for non-pillar-admin users"""

        new_org = {
            'name': 'Union of €-forgers',
            'seat_count': 5,
            'admin_uid': self.admin1_uid,
        }

        # Tests both as a POST and as a PUT request. Should have the same result (no creation).
        self.post('/api/organizations', auth_token=auth_token, json=new_org, expected_status=403)

        new_id = bson.ObjectId()
        self.put(f'/api/organizations/{new_id}',
                 auth_token=auth_token, json=new_org, expected_status=405)

    def test_create_as_admin1(self):
        self._create_test('admin1-token')

    def test_create_as_member(self):
        self._create_test('member1-token')
        self._create_test('member2-token')

    def test_create_as_outsider(self):
        self._create_test('outsider-token')

    def test_create_as_anonymous(self):
        self._create_test(None)


class OrganizationItemEveTest(AbstractPillarTest):
    """Test GET/PUT/DELETE access to Organization items"""

    def setUp(self, **kwargs):
        super().setUp(**kwargs)

        self.enter_app_context()
        self.om = self.app.org_manager

        # Create an organization with admin who is not organization member.
        self.admin_uid = self.create_user(24 * 'a', token='admin-token')
        org_doc = self.om.create_new_org('Хакеры', self.admin_uid, 25)
        self.org_id = org_doc['_id']

        # Create a member of the organization.
        self.member_uid = self.create_user(24 * 'b',
                                           email='member@example.com',
                                           token='member-token')
        self.om.assign_users(self.org_id, ['member@example.com'])

        # Create an outside user.
        self.outsider_uid = self.create_user(24 * '0', token='outsider-token')

        # Re-fetch the organization so that self.org_doc has the correct etag.
        self.org_doc = self._from_db()

    def _from_db(self) -> dict:
        return self.om._get_org(self.org_id)

    def test_get_admin(self):
        resp = self.get(f'/api/organizations/{self.org_id}',
                        auth_token='admin-token')
        org = resp.get_json()

        self.assertEqual(str(self.org_id), org['_id'])
        self.assertEqual(25, org['seat_count'])

    def test_get_member(self):
        resp = self.get(f'/api/organizations/{self.org_id}',
                        auth_token='member-token')
        org = resp.get_json()

        self.assertEqual(str(self.org_id), org['_id'])
        self.assertEqual(25, org['seat_count'])

    def test_get_outside_user(self):
        # Eve pretends the organization doesn't even exist when you don't have access.
        self.get(f'/api/organizations/{self.org_id}',
                 auth_token='outsider-token',
                 expected_status=404)

    def test_get_anonymous(self):
        self.get(f'/api/organizations/{self.org_id}',
                 expected_status=403)

    def _put_test(self, auth_token: typing.Optional[str]):
        """Generic PUT test, should be same result for all cases."""

        put_doc = remove_private_keys(self.org_doc)
        put_doc['name'] = 'new name'

        self.put(f'/api/organizations/{self.org_id}',
                 json=put_doc,
                 etag=self.org_doc['_etag'],
                 auth_token=auth_token,
                 expected_status=405)

        # The name shouldn't have changed in the database.
        db_org = self._from_db()
        self.assertEqual(self.org_doc['name'], db_org['name'])

    def test_put_admin(self):
        self._put_test('admin-token')

    def test_put_member(self):
        self._put_test('member-token')

    def test_put_outside_user(self):
        self._put_test('outsider-token')

    def test_put_anonymous(self):
        self._put_test(None)

    def _delete_test(self, auth_token: typing.Optional[str]):
        """Generic DELETE test, should be same result for all cases."""

        self.delete(f'/api/organizations/{self.org_id}',
                    etag=self.org_doc['_etag'],
                    auth_token=auth_token,
                    expected_status=405)

        # The organization shouldn't be deleted.
        db_org = self._from_db()
        self.assertFalse(db_org['_deleted'])

    def test_delete_admin(self):
        self._delete_test('admin-token')

    def test_delete_member(self):
        self._delete_test('member-token')

    def test_delete_outside_user(self):
        self._delete_test('outsider-token')

    def test_delete_anonymous(self):
        self._delete_test(None)


class UserCreationTest(AbstractPillarTest):
    def setUp(self, **kwargs):
        super().setUp(**kwargs)

        self.enter_app_context()
        self.om = self.app.org_manager

        # Create an organization with admin who is not organization member.
        self.admin_uid = self.create_user(24 * 'a', token='admin-token')
        org_doc = self.om.create_new_org('Хакеры', self.admin_uid, 25,
                                         org_roles={'org-크툴루'})
        self.org_id = org_doc['_id']

        self.om.assign_users(self.org_id, ['newmember@example.com'])

        # Re-fetch the organization so that self.org_doc has the correct etag.
        self.org_doc = self._from_db()

    def _from_db(self) -> dict:
        return self.om._get_org(self.org_id)

    @responses.activate
    def test_member_joins_later(self, **kwargs):
        # Mock a Blender ID response for this user.
        blender_id_response = {'status': 'success',
                               'user': {'email': 'newmember@example.com',
                                        'full_name': 'Our lord and saviour Cthulhu',
                                        'id': 9999},
                               'token_expires': 'Mon, 1 Jan 2218 01:02:03 GMT'}

        responses.add(responses.POST,
                      '%s/u/validate_token' % self.app.config['BLENDER_ID_ENDPOINT'],
                      json=blender_id_response,
                      status=200)

        # Create a user by authenticating
        resp = self.get('/api/users/me', auth_token='user-token')
        user_info = resp.get_json()
        my_id = bson.ObjectId(user_info['_id'])

        # Check that the user has the organization roles.
        users_coll = self.app.db('users')
        db_user = users_coll.find_one(my_id)
        self.assertEqual({'org-크툴루'}, set(db_user['roles']))

        # Check that the user is moved from 'unknown_members' to 'members' in the org.
        db_org = self._from_db()
        self.assertEqual([], db_org['unknown_members'])
        self.assertEqual([my_id], db_org['members'])
