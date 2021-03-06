"""Test cases for the zencoder notifications."""
import json

from pillar.tests import AbstractPillarTest


class ZencoderNotificationTest(AbstractPillarTest):

    def test_missing_secret(self):
        with self.app.test_request_context():
            resp = self.client.post('/api/encoding/zencoder/notifications')
        self.assertEqual(401, resp.status_code)

    def test_wrong_secret(self):
        with self.app.test_request_context():
            resp = self.client.post('/api/encoding/zencoder/notifications',
                                    headers={'X-Zencoder-Notification-Secret': 'koro'})
        self.assertEqual(401, resp.status_code)

    def test_good_secret_existing_file(self):
        self.ensure_file_exists(file_overrides={
            'processing': {'backend': 'zencoder',
                           'job_id': 'koro-007',
                           'status': 'processing'}
        })

        with self.app.test_request_context():
            secret = self.app.config['ZENCODER_NOTIFICATIONS_SECRET']
            resp = self.client.post('/api/encoding/zencoder/notifications',
                                    data=json.dumps({'job': {'id': 'koro-007',
                                                             'state': 'done'},
                                                     'outputs': [{
                                                         'format': 'jpg',
                                                         'height': 1080,
                                                         'width': 2048,
                                                         'file_size_in_bytes': 15,
                                                         'md5_checksum': None,
                                                     }],
                                                     'input': {
                                                         'duration_in_ms': 5000,
                                                     }}),
                                    headers={'X-Zencoder-Notification-Secret': secret,
                                             'Content-Type': 'application/json'})

        # TODO: check that the file in MongoDB is actually updated properly.
        self.assertEqual(204, resp.status_code)
