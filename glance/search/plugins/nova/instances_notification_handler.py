# Copyright (c) 2014 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from oslo_log import log as logging
import oslo_messaging

from glance.search.plugins import base
from glance.common import utils

LOG = logging.getLogger(__name__)


class InstanceHandler(base.NotificationBase):
    """Handles nova server notifications. These can come as a result of
    a user action (like a name change, state change etc) or as a result of
    periodic auditing notifications nova sends
    """
    def __init__(self, *args, **kwargs):
        super(InstanceHandler, self).__init__(*args, **kwargs)
        self.image_delete_keys = ['deleted_at', 'deleted',
                                  'is_public', 'properties']

    def process(self, ctxt, publisher_id, event_type, payload, metadata):
        try:
            actions = {
                # compute.instance.update seems to be the event set as a
                # result of a state change etc
                "compute.instance.update": self.create,
            }
            actions[event_type](payload)
            return oslo_messaging.NotificationResult.HANDLED
        except Exception as e:
            LOG.error(utils.exception_to_str(e))

    def create(self, payload):
        id = payload['instance_id']
        payload = self.format_server(payload)
        self.engine.index(
            index=self.index_name,
            doc_type=self.document_type,
            body=payload,
            id=id
        )

    def format_server(self, payload):
        # TODO: Maybe the index should be more similar to the notification
        # structure? Notifications have a LOT more information than do
        # what we can get from a single nova call, though missing some stuff,
        # notably networking info
        # https://wiki.openstack.org/wiki/SystemUsageData#compute.instance.update:
        print payload
        return dict(
            id=payload['instance_id'],
            instance_id=payload['instance_id'],
            name=payload['display_name'],
            status=payload['state'],
            owner=payload['tenant_id'],
            updated=datetime.datetime.utcnow(), # TODO: Not this.
            created=payload['created_at'].replace(" ", "T"),
            # networks=server.networks,  # TODO: Figure this out
            availability_zone=payload.get('availability_zone', None),
            image=dict(
                id=payload['image_meta']['base_image_ref'],
                kernel_id=payload['image_meta']['kernel_id'],
                #name=bizarrely not here
                container_format=payload['image_meta']['container_format'],
                disk_format=payload['image_meta']['disk_format'],
                min_disk=payload['image_meta']['min_disk'],
                min_ram=payload['image_meta']['min_ram'],
            ),
            flavor=dict(
                id=payload['instance_flavor_id'],
                name=payload['instance_type'],
            ),
            state_description=payload['state_description'],
            vcpus=payload['vcpus'],
            disk_gb=payload['disk_gb'],
            memory_mb=payload['memory_mb'],
        )
