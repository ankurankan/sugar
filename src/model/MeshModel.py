# Copyright (C) 2006-2007 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import gobject

from sugar.graphics.xocolor import XoColor
from sugar.presence import presenceservice
from sugar import activity

from model.BuddyModel import BuddyModel
from model.accesspointmodel import AccessPointModel
from hardware import hardwaremanager
from hardware import nmclient

class ActivityModel:
    def __init__(self, act, bundle):
        self.activity = act
        self.bundle = bundle

    def get_id(self):
        return self.activity.props.id
        
    def get_icon_name(self):
        return self.bundle.icon
    
    def get_color(self):
        return XoColor(self.activity.props.color)

    def get_bundle_id(self):
        return self.bundle.bundle_id

class MeshModel(gobject.GObject):
    __gsignals__ = {
        'activity-added':       (gobject.SIGNAL_RUN_FIRST,
                                 gobject.TYPE_NONE, ([gobject.TYPE_PYOBJECT])),
        'activity-removed':     (gobject.SIGNAL_RUN_FIRST,
                                 gobject.TYPE_NONE, ([gobject.TYPE_PYOBJECT])),
        'buddy-added':          (gobject.SIGNAL_RUN_FIRST,
                                 gobject.TYPE_NONE, ([gobject.TYPE_PYOBJECT])),
        'buddy-moved':          (gobject.SIGNAL_RUN_FIRST,
                                 gobject.TYPE_NONE,
                                ([gobject.TYPE_PYOBJECT,
                                  gobject.TYPE_PYOBJECT])),
        'buddy-removed':        (gobject.SIGNAL_RUN_FIRST,
                                 gobject.TYPE_NONE, ([gobject.TYPE_PYOBJECT])),
        'access-point-added':   (gobject.SIGNAL_RUN_FIRST,
                                 gobject.TYPE_NONE, ([gobject.TYPE_PYOBJECT])),
        'access-point-removed': (gobject.SIGNAL_RUN_FIRST,
                                 gobject.TYPE_NONE, ([gobject.TYPE_PYOBJECT])),
        'mesh-added':           (gobject.SIGNAL_RUN_FIRST,
                                 gobject.TYPE_NONE, ([gobject.TYPE_PYOBJECT])),
        'mesh-removed':         (gobject.SIGNAL_RUN_FIRST,
                                 gobject.TYPE_NONE, ([]))
    }

    def __init__(self):
        gobject.GObject.__init__(self)

        self._activities = {}
        self._buddies = {}
        self._access_points = {}
        self._mesh = None

        self._pservice = presenceservice.get_instance()
        self._pservice.connect("activity-appeared",
                               self._activity_appeared_cb)
        self._pservice.connect('activity-disappeared',
                               self._activity_disappeared_cb)
        self._pservice.connect("buddy-appeared",
                               self._buddy_appeared_cb)
        self._pservice.connect("buddy-disappeared",
                               self._buddy_disappeared_cb)

        # Add any buddies the PS knows about already
        self._pservice.get_buddies_async(reply_handler=self._get_buddies_cb)

        self._pservice.get_activities_async(
                reply_handler=self._get_activities_cb)

        network_manager = hardwaremanager.get_network_manager()
        if network_manager:
            for nm_device in network_manager.get_devices():
                self._add_network_device(nm_device)
            network_manager.connect('device-added',
                                    self._nm_device_added_cb)
            network_manager.connect('device-removed',
                                    self._nm_device_removed_cb)

    def _get_buddies_cb(self, buddy_list):
        for buddy in buddy_list:
            self._buddy_appeared_cb(self._pservice, buddy)

    def _get_activities_cb(self, activity_list):
        for act in activity_list:
            self._check_activity(act)

    def _nm_device_added_cb(self, manager, nm_device):
        self._add_network_device(nm_device)

    def _nm_device_removed_cb(self, manager, nm_device):
        self._remove_network_device(nm_device)

    def _nm_network_appeared_cb(self, nm_device, nm_network):
        self._add_access_point(nm_device, nm_network)

    def _nm_network_disappeared_cb(self, nm_device, nm_network):
        if self._access_points.has_key(nm_network.get_op()):
            ap = self._access_points[nm_network.get_op()]
            self._remove_access_point(ap)

    def _add_network_device(self, nm_device):
        dtype = nm_device.get_type()
        if dtype == nmclient.DEVICE_TYPE_802_11_WIRELESS:
            for nm_network in nm_device.get_networks():
                self._add_access_point(nm_device, nm_network)

            nm_device.connect('network-appeared',
                              self._nm_network_appeared_cb)
            nm_device.connect('network-disappeared',
                              self._nm_network_disappeared_cb)
        elif dtype == nmclient.DEVICE_TYPE_802_11_MESH_OLPC:
            self._mesh = nm_device
            self.emit('mesh-added', self._mesh)

    def _remove_network_device(self, nm_device):
        if nm_device == self._mesh:
            self._mesh = None
            self.emit('mesh-removed')
        elif nm_device.get_type() == nmclient.DEVICE_TYPE_802_11_WIRELESS:
            aplist = self._access_points.values()
            for ap in aplist:
                if ap.get_nm_device() == nm_device:
                    self._remove_access_point(ap)

    def _add_access_point(self, nm_device, nm_network):
        model = AccessPointModel(nm_device, nm_network)
        self._access_points[model.get_id()] = model
        self.emit('access-point-added', model)

    def _remove_access_point(self, ap):
        if not self._access_points.has_key(ap.get_id()):
            return
        self.emit('access-point-removed', ap)
        del self._access_points[ap.get_id()]

    def get_mesh(self):
        return self._mesh

    def get_access_points(self):
        return self._access_points.values()

    def get_activities(self):
        return self._activities.values()

    def get_buddies(self):
        return self._buddies.values()

    def _buddy_activity_changed_cb(self, model, cur_activity):
        if not self._buddies.has_key(model.get_buddy().object_path()):
            return
        if cur_activity and self._activities.has_key(cur_activity.props.id):
            activity_model = self._activities[cur_activity.props.id]
            self.emit('buddy-moved', model, activity_model)
        else:
            self.emit('buddy-moved', model, None)

    def _buddy_appeared_cb(self, pservice, buddy):
        if self._buddies.has_key(buddy.object_path()):
            return

        model = BuddyModel(buddy=buddy)
        model.connect('current-activity-changed',
                      self._buddy_activity_changed_cb)
        self._buddies[buddy.object_path()] = model
        self.emit('buddy-added', model)

        cur_activity = buddy.props.current_activity
        if cur_activity:
            self._buddy_activity_changed_cb(model, cur_activity)

    def _buddy_disappeared_cb(self, pservice, buddy):
        if not self._buddies.has_key(buddy.object_path()):
            return
        self.emit('buddy-removed', self._buddies[buddy.object_path()])
        del self._buddies[buddy.object_path()]

    def _activity_appeared_cb(self, pservice, act):
        self._check_activity(act)

    def _check_activity(self, presence_activity):
        registry = activity.get_registry()
        bundle = registry.get_activity(presence_activity.props.type)
        if not bundle:
            return
        if self.has_activity(presence_activity.props.id):
            return
        self.add_activity(bundle, presence_activity)

    def has_activity(self, activity_id):
        return self._activities.has_key(activity_id)

    def get_activity(self, activity_id):
        if self.has_activity(activity_id):
            return self._activities[activity_id]
        else:
            return None

    def add_activity(self, bundle, act):
        model = ActivityModel(act, bundle)
        self._activities[model.get_id()] = model
        self.emit('activity-added', model)

        for buddy in self._pservice.get_buddies():
            cur_activity = buddy.props.current_activity
            object_path = buddy.object_path()
            if cur_activity == activity and object_path in self._buddies:
                buddy_model = self._buddies[object_path]
                self.emit('buddy-moved', buddy_model, model)

    def _activity_disappeared_cb(self, pservice, act):
        if self._activities.has_key(act.props.id):
            activity_model = self._activities[act.props.id]
            self.emit('activity-removed', activity_model)
            del self._activities[act.props.id]
