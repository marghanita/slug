#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=4 sw=4 et sts=4 ai:

"""Module for creating and editing Event objects."""

import config
config.setup()

# Python Imports
import os
import os.path
import traceback
import cStringIO as StringIO
from datetime import datetime

# AppEngine Imports
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from django import template

# Third Party imports
import aeoid.middleware
from dateutil import rrule
from datetime_tz import datetime_tz
import markdown
import logging

# Our App imports
import models
from utils.render import render as r


# We don't want to wrap this line as we use a grep to extract the details
# pylint: disable-msg=C0301
extensions = ['abbr', 'footnotes', 'def_list', 'fenced_code', 'tables', 'subscript', 'superscript', 'slugheader', 'anyurl']


def lastfridays():
    """Return 5 last Fridays of the month."""
    return list(x.date() for x in rrule.rrule(
         rrule.MONTHLY, interval=1, count=10, byweekday=(rrule.FR(-1)),
         dtstart=datetime.now()))


def get_templates():
    """Get all the markdown templates."""
    ret = []

    directory = "templates/markdown"
    for filename in os.listdir(directory):
        if not filename.endswith('.md'):
            continue

        fullpath = os.path.join(directory, filename)
        name = filename.replace('.md', '')
        ret.append((name, file(fullpath).read()))
    return ret


class EditEvent(webapp.RequestHandler):
    """Handler for creating and editing Event objects."""

    def get(self, key=None):
        if key:
            try:
                key = long(key)
                event = models.Event.get_by_id(key)
                assert event
            # pylint: disable-msg=W0702
            except (AssertionError, ValueError):
                self.redirect('/events')
                return
        else:
            event = None

        fridays = lastfridays()
        templates = get_templates()

        self.response.out.write(r(
            'templates/editevent.html', locals()
            ))

    def post(self, key=None):
        event_name = self.request.get('name')
        if key:
            try:
                key = long(key)
                event = models.Event.get_by_id(key)
                event.name = event_name
            # pylint: disable-msg=W0702
            except (AssertionError, ValueError):
                self.redirect('/events')
                return
        else:
            #name is a required field; must populate now. Rest comes later.
            event = models.Event(name=event_name, text='', html='',
                    start=datetime.now(), end=datetime.now())

        inputtext = self.request.get('input')

        start_date = datetime_tz.smartparse(self.request.get('start'))
        end_date = datetime_tz.smartparse(self.request.get('end'))

        event.input = inputtext
        event.start = start_date.asdatetime()
        event.end = end_date.asdatetime()

        event.put()

        # We can't do this template subsitution until we have saved the event.
        try:
            plaintext = str(template.Template(inputtext).render(
                            template.Context({'event': event, 'req': self.request}), ))
            html = markdown.markdown(plaintext, extensions).encode('utf-8')
            event.plaintext = plaintext
            event.html = html
        except Exception, e:
            sio = StringIO.StringIO()
            traceback.print_exc(file=sio)
            event.plaintext = sio.getvalue()

        logging.debug("e.a %s, e.n %s", event.announcement, event.name)

        if not event.published:
            #Until event is published, keep event and announcement in sync
            #After publishing, don't - only update the announcement when we
            #republish
            if event.announcement:
                announcement = event.announcement
                announcement.name = event.name
            else:
                announcement = models.Announcement(name=event.name)
            announcement.plaintext = event.plaintext
            announcement.html = event.html
            event.announcement = announcement.put()

        event.put()

        self.redirect('%s/edit' % event.get_url())


application = webapp.WSGIApplication(
    [('/event/add', EditEvent),
     ('/event/(.*)/edit', EditEvent)],
    debug=True)
application = aeoid.middleware.AeoidMiddleware(application)


def main():
    run_wsgi_app(application)


if __name__ == "__main__":
    main()
