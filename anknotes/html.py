import re
from HTMLParser import HTMLParser


from anknotes.constants import SETTINGS
from anknotes.base import is_str, decode
from anknotes.db import get_evernote_title_from_guid
from anknotes.logging import log

try:
    from aqt import mw
except Exception:
    pass


class MLStripper(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.reset()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return ''.join(self.fed)


def strip_tags(html, strip_entities=False):
    __html_entity_repl = '_!_DONT_STRIP_HTML_ENTITIES_!_'
    if html is None:
        return None
    if not strip_entities:
        html = html.replace('&', __html_entity_repl)
    s = MLStripper()
    s.feed(html)
    html = s.get_data()
    if not strip_entities:
        html = html.replace(__html_entity_repl, '&')
    return html
    # s = MLStripper()
    # s.feed(html)
    # return s.get_data()


def strip_tags_and_new_lines(html):
    if html is None:
        return None
    return re.sub(r'[\r\n]+', ' ', strip_tags(html))


__text_escape_phrases = u'&|&amp;|\'|&apos;|"|&quot;|>|&gt;|<|&lt;'.split('|')


def escape_text(title):
    global __text_escape_phrases
    for i in range(0, len(__text_escape_phrases), 2):
        title = title.replace(__text_escape_phrases[i], __text_escape_phrases[i + 1])
    return title


def unescape_text(title, try_decoding=False):
    title_orig = title
    global __text_escape_phrases
    if try_decoding:
        title = decode(title)
    try:
        for i in range(0, len(__text_escape_phrases), 2):
            title = title.replace(__text_escape_phrases[i + 1], __text_escape_phrases[i])
        title = title.replace(u"&nbsp;", u" ")
    except Exception:
        if try_decoding:
            raise UnicodeError
        title_new = unescape_text(title, True)
        log(title + '\n' + title_new + '\n\n', 'unicode')
        return title_new
    return title


def clean_title(title):
    title = unescape_text(decode(title))
    title = re.sub(r'( |\xa0)+', ' ', decode(title))
    return title


def generate_evernote_url(guid):
    ids = get_evernote_account_ids()
    return u'evernote:///view/%s/%s/%s/%s/' % (ids.uid, ids.shard, guid, guid)


def generate_evernote_link_by_type(guid, title=None, link_type=None, value=None, escape=True):
    url = generate_evernote_url(guid)
    if not title:
        title = get_evernote_title_from_guid(guid)
    if escape:
        title = escape_text(title)
    style = generate_evernote_html_element_style_attribute(link_type, value)
    html = u"""<a href="%s"><span style="%s">%s</span></a>""" % (url, style, title)
    # print html
    return html


def generate_evernote_link(guid, title=None, value=None, escape=True):
    return generate_evernote_link_by_type(guid, title, 'Links', value, escape=escape)


def generate_evernote_link_by_level(guid, title=None, value=None, escape=True):
    return generate_evernote_link_by_type(guid, title, 'Levels', value, escape=escape)


def generate_evernote_html_element_style_attribute(link_type, value, bold=True, group=None):
    global evernote_link_colors
    colors = None
    if link_type in evernote_link_colors:
        color_types = evernote_link_colors[link_type]
        if link_type is 'Levels':
            if not value:
                value = 1
            if not group:
                group = 'OL' if isinstance(value, int) else 'Modifiers'
            if not value in color_types[group]:
                group = 'Headers'
            if value in color_types[group]:
                colors = color_types[group][value]
        elif link_type is 'Links':
            if not value:
                value = 'Default'
            if value in color_types:
                colors = color_types[value]
    if not colors:
        colors = evernote_link_colors['Default']
    colorDefault = colors
    if not is_str_type(colorDefault):
        colorDefault = colorDefault['Default']
    if not colorDefault[-1] is ';':
        colorDefault += ';'
    style = 'color: ' + colorDefault
    if bold:
        style += 'font-weight:bold;'
    return style


def generate_evernote_span(title=None, element_type=None, value=None, guid=None, bold=True, escape=True):
    assert title or guid
    if not title:
        title = get_evernote_title_from_guid(guid)
    if escape:
        title = escape_text(title)
    style = generate_evernote_html_element_style_attribute(element_type, value, bold)
    html = u"""<span style="%s">%s</span>""" % (style, title)
    return html


evernote_link_colors = {
    'Levels': {
        'OL':        {
            1: {
                'Default': 'rgb(106, 0, 129);',
                'Hover':   'rgb(168, 0, 204);'
            },
            2: {
                'Default': 'rgb(235, 0, 115);',
                'Hover':   'rgb(255, 94, 174);'
            },
            3: {
                'Default': 'rgb(186, 0, 255);',
                'Hover':   'rgb(213, 100, 255);'
            },
            4: {
                'Default': 'rgb(129, 182, 255);',
                'Hover':   'rgb(36, 130, 255);'
            },
            5: {
                'Default': 'rgb(232, 153, 220);',
                'Hover':   'rgb(142, 32, 125);'
            },
            6: {
                'Default': 'rgb(201, 213, 172);',
                'Hover':   'rgb(130, 153, 77);'
            },
            7: {
                'Default': 'rgb(231, 179, 154);',
                'Hover':   'rgb(215, 129, 87);'
            },
            8: {
                'Default': 'rgb(249, 136, 198);',
                'Hover':   'rgb(215, 11, 123);'
            }
        },
        'Headers':   {
            'Auto TOC': 'rgb(11, 59, 225);'
        },
        'Modifiers': {
            'Orange':                 'rgb(222, 87, 0);',
            'Orange (Light)':         'rgb(250, 122, 0);',
            'Dark Red/Pink':          'rgb(164, 15, 45);',
            'Pink Alternative LVL1:': 'rgb(188, 0, 88);'
        }
    },
    'Titles': {
        'Field Title Prompt': 'rgb(169, 0, 48);'
    },
    'Links':  {
        'See Also': {
            'Default': 'rgb(45, 79, 201);',
            'Hover':   'rgb(108, 132, 217);'
        },
        'TOC':      {
            'Default': 'rgb(173, 0, 0);',
            'Hover':   'rgb(196, 71, 71);'
        },
        'Outline':  {
            'Default': 'rgb(105, 170, 53);',
            'Hover':   'rgb(135, 187, 93);'
        },
        'AnkNotes': {
            'Default': 'rgb(30, 155, 67);',
            'Hover':   'rgb(107, 226, 143);'
        }
    }
}

evernote_link_colors['Default'] = evernote_link_colors['Links']['Outline']
evernote_link_colors['Links']['Default'] = evernote_link_colors['Default']

enAccountIDs = None


def get_evernote_account_ids():
    global enAccountIDs
    if not enAccountIDs or not enAccountIDs.Valid:
        enAccountIDs = EvernoteAccountIDs()
    return enAccountIDs


def tableify_column(column):
    return str(column).replace('\n', '\n<BR>').replace('  ', '&nbsp;&nbsp;')


def tableify_lines(rows, columns=None, tr_index_offset=0, return_html=True):
    if columns is None:
        columns = []
    elif not isinstance(columns, list):
        columns = [columns]
    trs = ['<tr class="tr%d%s">%s\n</tr>\n' % (i_row, ' alt' if i_row % 2 is 0 else ' std', ''.join(
        ['\n <td class="td%d%s">%s</td>' % (i_col + 1, ' alt' if i_col % 2 is 0 else ' std', tableify_column(column))
         for i_col, column in enumerate(row if isinstance(row, list) else row.split('|'))])) for i_row, row in
           enumerate(columns + rows)]
    if return_html:
        return "<table cellspacing='0' style='border: 1px solid black;border-collapse: collapse;'>\n%s</table>" % ''.join(
            trs)
    return trs


class EvernoteAccountIDs:
    uid = SETTINGS.EVERNOTE.ACCOUNT.UID_DEFAULT_VALUE
    shard = SETTINGS.EVERNOTE.ACCOUNT.SHARD_DEFAULT_VALUE

    @property
    def Valid(self):
        return self.is_valid()

    def is_valid(self, uid=None, shard=None):
        if uid is None:
            uid = self.uid
        if shard is None:
            shard = self.shard
        if not uid or not shard:
            return False
        if uid == '0' or uid == SETTINGS.EVERNOTE.ACCOUNT.UID.val or not unicode(
                uid).isnumeric(): return False
        if shard == 's999' or uid == SETTINGS.EVERNOTE.ACCOUNT.SHARD.val or shard[0] != 's' or not unicode(
                shard[1:]).isnumeric(): return False
        return True

    def __init__(self, uid=None, shard=None):
        if uid and shard:
            if self.update(uid, shard):
                return
        try:
            self.uid = SETTINGS.EVERNOTE.ACCOUNT.UID.fetch()
            self.shard = SETTINGS.EVERNOTE.ACCOUNT.SHARD.fetch()
            if self.Valid:
                return
        except Exception:
            pass
        self.uid = SETTINGS.EVERNOTE.ACCOUNT.UID.val
        self.shard = SETTINGS.EVERNOTE.ACCOUNT.SHARD.val

    def update(self, uid, shard):
        if not self.is_valid(uid, shard):
            return False
        try:
            SETTINGS.EVERNOTE.ACCOUNT.UID.save(uid)
            SETTINGS.EVERNOTE.ACCOUNT.SHARD.save(shard)
        except Exception:
            return False
        self.uid = uid
        self.shard = shard
        return self.Valid
