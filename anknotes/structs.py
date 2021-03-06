import re
# from BeautifulSoup import UnicodeDammit
import anknotes
from bs4 import UnicodeDammit


from anknotes.constants import *
from anknotes.base import item_to_set, item_to_list
from anknotes.db import *
from anknotes.enum import Enum
from anknotes.html import strip_tags
from anknotes.logging import PadList, JoinList
from anknotes.enums import *
from anknotes.EvernoteNoteTitle import EvernoteNoteTitle


# from evernote.edam.notestore.ttypes import NoteMetadata, NotesMetadataList

def upperFirst(name):
    return name[0].upper() + name[1:]


def getattrcallable(obj, attr):
    val = getattr(obj, attr)
    if callable(val):
        return val()
    return val


# from anknotes.EvernoteNotePrototype import EvernoteNotePrototype
# from anknotes.EvernoteNoteTitle import EvernoteNoteTitle

class EvernoteStruct(object):
    success = False
    Name = ""
    Guid = ""
    _sql_columns_ = "name"
    _sql_table_ = TABLES.EVERNOTE.TAGS
    _sql_where_ = "guid"
    _attr_order_ = None
    _additional_attr_ = None
    _title_is_note_title_ = False

    @staticmethod
    def _attr_from_key_(key):
        return upperFirst(key)

    def keys(self):
        return self._valid_attributes_()

    def items(self):
        return [self.getAttribute(key) for key in self._attr_order_]

    def sqlUpdateQuery(self):
        columns = self._attr_order_ if self._attr_order_ else self._sql_columns_
        return "INSERT OR REPLACE INTO `%s`(%s) VALUES (%s)" % (
            self._sql_table_, '`' + '`,`'.join(columns) + '`', ', '.join(['?'] * len(columns)))

    def sqlSelectQuery(self, allColumns=True):
        return "SELECT %s FROM %s WHERE %s = ?" % (
            '*' if allColumns else ','.join(self._sql_columns_), self._sql_table_, self._sql_where_)

    def getFromDB(self, allColumns=True):
        ankDB().setrowfactory()
        result = ankDB().first(self.sqlSelectQuery(allColumns), self.Where)
        if result:
            self.success = True
            self.setFromKeyedObject(result)
        else:
            self.success = False
        return self.success

    @property
    def Where(self):
        return self.getAttribute(self._sql_where_)

    @Where.setter
    def Where(self, value):
        self.setAttribute(self._sql_where_, value)

    def getAttribute(self, key, default=None, raiseIfInvalidKey=False):
        if not self.hasAttribute(key):
            if raiseIfInvalidKey:
                raise KeyError
            return default
        return getattr(self, self._attr_from_key_(key))

    def hasAttribute(self, key):
        return hasattr(self, self._attr_from_key_(key))

    def setAttribute(self, key, value):
        if key == "fetch_" + self._sql_where_:
            self.setAttribute(self._sql_where_, value)
            self.getFromDB()
        elif self._is_valid_attribute_(key):
            setattr(self, self._attr_from_key_(key), value)
        else:
            raise KeyError("%s: %s is not a valid attribute" % (self.__class__.__name__, key))

    def setAttributeByObject(self, key, keyed_object):
        self.setAttribute(key, keyed_object[key])

    def setFromKeyedObject(self, keyed_object, keys=None):
        """

        :param keyed_object:
        :type: sqlite.Row | dict[str, object] | re.MatchObject | _sre.SRE_Match
        :return:
        """
        lst = self._valid_attributes_()
        if keys or isinstance(keyed_object, dict):
            pass
        elif isinstance(keyed_object, type(re.search('', ''))):
            regex_attr = 'wholeRegexMatch'
            self._additional_attr_.add(regex_attr)
            whole_match = keyed_object.group(0)
            keyed_object = keyed_object.groupdict()
            keyed_object[regex_attr] = whole_match
        elif hasattr(keyed_object, 'keys'):
            keys = getattrcallable(keyed_object, 'keys')
        elif hasattr(keyed_object, self._sql_where_):
            for key in self.keys():
                if hasattr(keyed_object, key):
                    self.setAttribute(key, getattr(keyed_object, key))
            return True
        else:
            return False

        if keys is None:
            keys = keyed_object
        for key in keys:
            if key == "fetch_" + self._sql_where_:
                self.Where = keyed_object[key]
                self.getFromDB()
            elif key in lst:
                self.setAttributeByObject(key, keyed_object)
        return True

    def setFromListByDefaultOrder(self, args):
        max = len(self._attr_order_)
        for i, value in enumerate(args):
            if i > max:
                raise Exception("Argument #%d for %s (%s) exceeds the default number of attributes for the class." % (
                    i, self.__class__.__name__, str(value)))
            self.setAttribute(self._attr_order_[i], value)

    def _valid_attributes_(self):
        return self._additional_attr_.union(self._sql_columns_, [self._sql_where_], self._attr_order_)

    def _is_valid_attribute_(self, attribute):
        return (attribute[0].lower() + attribute[1:]) in self._valid_attributes_()

    def __init__(self, *args, **kwargs):
        if self._attr_order_ is None:
            self._attr_order_ = []
        if self._additional_attr_ is None:
            self._additional_attr_ = set()
        self._sql_columns_ = item_to_list(self._sql_columns_, chrs=' ,;')
        self._attr_order_ = item_to_list(self._attr_order_, chrs=' ,;')
        self._additional_attr_ = item_to_set(self._additional_attr_, chrs=' ,;')
        args = list(args)
        if args and self.setFromKeyedObject(args[0]):
            del args[0]
        self.setFromListByDefaultOrder(args)
        self.setFromKeyedObject(kwargs)


class EvernoteNotebook(EvernoteStruct):
    Stack = ""
    _sql_columns_ = ["name", "stack"]
    _sql_table_ = TABLES.EVERNOTE.NOTEBOOKS


class EvernoteTag(EvernoteStruct):
    ParentGuid = ""
    UpdateSequenceNum = -1
    _sql_columns_ = ["name", "parentGuid"]
    _sql_table_ = TABLES.EVERNOTE.TAGS
    _attr_order_ = 'guid|name|parentGuid|updateSequenceNum'


class EvernoteLink(EvernoteStruct):
    _uid_ = -1
    Shard = 'x999'
    Guid = ""
    WholeRegexMatch = ""
    _title_ = None
    """:type: EvernoteNoteTitle.EvernoteNoteTitle """
    _attr_order_ = 'uid|shard|guid|title'

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)

    @property
    def HTML(self):
        return self.Title.HTML

    @property
    def Title(self):
        """:rtype : EvernoteNoteTitle.EvernoteNoteTitle"""
        return self._title_

    @property
    def FullTitle(self): return self.Title.FullTitle

    @Title.setter
    def Title(self, value):
        """
        :param value:
        :type value : EvernoteNoteTitle.EvernoteNoteTitle | str | unicode
        :return:
        """
        self._title_ = anknotes.EvernoteNoteTitle.EvernoteNoteTitle(value)
        """:type : EvernoteNoteTitle.EvernoteNoteTitle"""

    @property
    def Uid(self):
        return int(self._uid_)

    @Uid.setter
    def Uid(self, value):
        self._uid_ = int(value)

    @property
    def NoteTitle(self):
        f = anknotes.EvernoteNoteFetcher.EvernoteNoteFetcher(guid=self.Guid, use_local_db_only=True)
        if not f.getNote():
            return "<Invalid Note>"
        return f.result.Note.FullTitle

    def __str__(self):
        return "<%s> %s: %s" % (self.__class__.__name__, self.Guid, self.FullTitle)

    def __repr__(self):
        # id =
        return "<%s> %s: %s" % (self.__class__.__name__, self.Guid, self.NoteTitle)


class EvernoteTOCEntry(EvernoteStruct):
    RealTitle = ""
    """:type : str"""
    OrderedList = ""
    """
    HTML output of Root Title's Ordererd List
    :type : str
    """
    TagNames = ""
    """:type : str"""
    NotebookGuid = ""

    def __init__(self, *args, **kwargs):
        self._attr_order_ = 'realTitle|orderedList|tagNames|notebookGuid'
        super(self.__class__, self).__init__(*args, **kwargs)


class EvernoteValidationEntry(EvernoteStruct):
    Guid = ""
    """:type : str"""
    Title = ""
    """:type : str"""
    Contents = ""
    """:type : str"""
    TagNames = ""
    """:type : str"""
    NotebookGuid = ""
    NoteType = ""

    def __init__(self, *args, **kwargs):
        # spr = super(self.__class__ , self)
        # spr._attr_order_ = self._attr_order_
        # spr.__init__(*args, **kwargs)
        self._attr_order_ = 'guid|title|contents|tagNames|notebookGuid|noteType'
        super(self.__class__, self).__init__(*args, **kwargs)


class EvernoteAPIStatusOld(AutoNumber):
    Uninitialized = -100
    """:type : EvernoteAPIStatus"""
    EmptyRequest = -3
    """:type : EvernoteAPIStatus"""
    Manual = -2
    """:type : EvernoteAPIStatus"""
    RequestQueued = -1
    """:type : EvernoteAPIStatus"""
    Success = 0
    """:type : EvernoteAPIStatus"""
    RateLimitError = ()
    """:type : EvernoteAPIStatus"""
    SocketError = ()
    """:type : EvernoteAPIStatus"""
    UserError = ()
    """:type : EvernoteAPIStatus"""
    NotFoundError = ()
    """:type : EvernoteAPIStatus"""
    UnhandledError = ()
    """:type : EvernoteAPIStatus"""
    Unknown = 100
    """:type : EvernoteAPIStatus"""

    def __getitem__(self, item):
        """:rtype : EvernoteAPIStatus"""

        return super(self.__class__, self).__getitem__(item)

    # def __new__(cls, *args, **kwargs):
    #     """:rtype : EvernoteAPIStatus"""
    #     return type(cls).__new__(*args, **kwargs)

    @property
    def IsError(self):
        return EvernoteAPIStatus.Unknown.value > self.value > EvernoteAPIStatus.Success.value

    @property
    def IsSuccessful(self):
        return EvernoteAPIStatus.Success.value >= self.value > EvernoteAPIStatus.Uninitialized.value

    @property
    def IsSuccess(self):
        return self == EvernoteAPIStatus.Success


class EvernoteAPIStatus(AutoNumberedEnum):
    Uninitialized = -100
    """:type : EvernoteAPIStatus"""
    Initialized = -75
    """:type : EvernoteAPIStatus"""
    UnableToFindStatus = -70
    """:type : EvernoteAPIStatus"""
    InvalidStatus = -60
    """:type : EvernoteAPIStatus"""
    Cancelled = -50
    """:type : EvernoteAPIStatus"""
    Disabled = -25
    """:type : EvernoteAPIStatus"""
    Unchanged = -15
    """:type : EvernoteAPIStatus"""
    EmptyRequest = -10
    """:type : EvernoteAPIStatus"""
    Manual = -5
    """:type : EvernoteAPIStatus"""
    RequestSkipped = -4
    """:type : EvernoteAPIStatus"""
    RequestQueued = -3
    """:type : EvernoteAPIStatus"""
    ExceededLocalLimit = -2
    """:type : EvernoteAPIStatus"""
    DelayedDueToRateLimit = -1
    """:type : EvernoteAPIStatus"""
    Success = 0
    """:type : EvernoteAPIStatus"""
    RateLimitError = ()
    """:type : EvernoteAPIStatus"""
    SocketError = ()
    """:type : EvernoteAPIStatus"""
    UserError = ()
    """:type : EvernoteAPIStatus"""
    UnchangedError = ()
    """:type : EvernoteAPIStatus"""
    NotFoundError = ()
    """:type : EvernoteAPIStatus"""
    MissingDataError = ()
    """:type : EvernoteAPIStatus"""
    UnhandledError = ()
    """:type : EvernoteAPIStatus"""
    GenericError = ()
    """:type : EvernoteAPIStatus"""
    Unknown = 100
    """:type : EvernoteAPIStatus"""

    # def __new__(cls, *args, **kwargs):
    #     """:rtype : EvernoteAPIStatus"""
    #     return type(cls).__new__(*args, **kwargs)

    @property
    def IsError(self):
        return EvernoteAPIStatus.Unknown.value > self.value > EvernoteAPIStatus.Success.value

    @property
    def IsDelayableError(self):
        return self.value == EvernoteAPIStatus.RateLimitError.value or self.value == EvernoteAPIStatus.SocketError.value

    @property
    def IsSuccessful(self):
        return EvernoteAPIStatus.Success.value >= self.value >= EvernoteAPIStatus.Manual.value

    @property
    def IsSuccess(self):
        return self == EvernoteAPIStatus.Success


class EvernoteImportType:
    Add, UpdateInPlace, DeleteAndUpdate = range(3)


class EvernoteNoteFetcherResult(object):
    def __init__(self, note=None, status=None, source=-1):
        """

        :type note: EvernoteNotePrototype.EvernoteNotePrototype
        :type status: EvernoteAPIStatus
        """
        if not status:
            status = EvernoteAPIStatus.Uninitialized
        self.Note = note
        self.Status = status
        self.Source = source


class EvernoteNoteFetcherResults(object):
    Status = EvernoteAPIStatus.Uninitialized
    ImportType = EvernoteImportType.Add
    Local = 0
    Notes = []
    Imported = 0
    Max = 0
    AlreadyUpToDate = 0

    @property
    def DownloadSuccess(self):
        return self.Count == self.Max

    @property
    def AnkiSuccess(self):
        return self.Imported == self.Count

    @property
    def TotalSuccess(self):
        return self.DownloadSuccess and self.AnkiSuccess

    @property
    def LocalDownloadsOccurred(self):
        return self.Local > 0

    @property
    def Remote(self):
        return self.Count - self.Local

    @property
    def SummaryShort(self):
        add_update_strs = ['New', "Added"] if self.ImportType == EvernoteImportType.Add else  ['Existing',
                                                                                               'Updated In-Place' if self.ImportType == EvernoteImportType.UpdateInPlace else 'Deleted and Updated']
        return "%d %s Notes Have Been %s" % (self.Imported, add_update_strs[0], add_update_strs[1])

    @property
    def SummaryLines(self):
        if self.Max is 0:
            return []
        add_update_strs = ['New', "Added to"] if self.ImportType == EvernoteImportType.Add else  ['Existing',
                                                                                                  "%s in" % (
                                                                                                      'Updated In-Place' if self.ImportType == EvernoteImportType.UpdateInPlace else 'Deleted and Updated')]
        add_update_strs[1] += " Anki"

        ## Evernote Status
        if self.DownloadSuccess:
            line = "All %3d" % self.Max
        else:
            line = "%3d of %3d" % (self.Count, self.Max)
        lines = [line + " %s Evernote Metadata Results Were Successfully Downloaded%s." % (
            add_update_strs[0], (' And %s' % add_update_strs[1]) if self.AnkiSuccess else '')]
        if self.Status.IsError:
            lines.append("-An error occurred during download (%s)." % str(self.Status))

        ## Local Calls
        if self.LocalDownloadsOccurred:
            lines.append(
                "-%3d %s note%s unexpectedly found in the local db and did not require an API call." % (
                    self.Local, add_update_strs[0], 's were' if self.Local > 1 else ' was'))
            lines.append("-%3d %s note(s) required an API call" % (self.Remote, add_update_strs[0]))
        if not self.ImportType == EvernoteImportType.Add and self.AlreadyUpToDate > 0:
            lines.append(
                "-%3d existing note%s already up-to-date with Evernote's servers, so %s not retrieved." % (
                    self.AlreadyUpToDate, 's are' if self.Local > 1 else ' is',
                    'they were' if self.Local > 1 else 'it was'))

        ## Anki Status
        if self.DownloadSuccess:
            return lines
        if self.AnkiSuccess:
            line = "All %3d" % self.Imported
        else:
            line = "%3d of %3d" % (self.Imported, self.Count)
        lines.append(line + " %s Downloaded Evernote Notes Have Been Successfully %s." % (
            add_update_strs[0], add_update_strs[1]))

        return lines

    @property
    def Summary(self):
        lines = self.SummaryLines
        if len(lines) is 0:
            return ''
        return '<BR>   - '.join(lines)

    @property
    def Count(self):
        return len(self.Notes)

    @property
    def EvernoteFails(self):
        return self.Max - self.Count

    @property
    def AnkiFails(self):
        return self.Count - self.Imported

    def __init__(self, status=None, local=None):
        """
        :param status:
        :type status : EvernoteAPIStatus
        :param local:
        :return:
        """
        if not status:
            status = EvernoteAPIStatus.Uninitialized
        if not local:
            local = 0
        self.Status = status
        self.Local = local
        self.Imported = 0
        self.Notes = []
        """
        :type : list[EvernoteNotePrototype.EvernoteNotePrototype]
        """

    def reportResult(self, result):
        """
        :type result : EvernoteNoteFetcherResult
        """
        self.Status = result.Status
        if self.Status == EvernoteAPIStatus.Success:
            self.Notes.append(result.Note)
            if result.Source == 1:
                self.Local += 1


class EvernoteImportProgress:
    class _GUIDs:
        Anki = None
        """:type : anknotes.Anki.Anki"""
        Local = None
        _anki_note_ids_ = None

        class Server:
            All = None
            New = None

            class Existing:
                All = None
                UpToDate = None
                OutOfDate = None

        def __init__(self, anki=None, anki_note_ids=None):
            if anki is None:
                return
            self.Anki = anki
            self._anki_note_ids_ = anki_note_ids
            self.Server.All, self.Server.New = set(), set()
            self.Server.Existing.All, self.Server.Existing.UpToDate, self.Server.Existing.OutOfDate = set(), set(), set()

        def setup(self, anki_note_ids=None):
            if not anki_note_ids:
                anki_note_ids = self._anki_note_ids_ or self.Anki.get_anknotes_note_ids()
            self.Local = self.Anki.get_evernote_guids_from_anki_note_ids(anki_note_ids)

        def loadNew(self, server_evernote_guids=None):
            if server_evernote_guids:
                self.Server.All = server_evernote_guids
            if not self.Server.All:
                return
            if not self.Local:
                self.setup()
            setServer = set(self.Server.All)
            self.Server.New = setServer - set(self.Local)
            self.Server.Existing.All = setServer - set(self.Server.New)

    class Results:
        Adding = None
        """:type : EvernoteNoteFetcherResults"""
        Updating = None
        """:type : EvernoteNoteFetcherResults"""

    GUIDs = None

    @property
    def Adding(self):
        return len(self.GUIDs.Server.New)

    @property
    def Updating(self):
        return len(self.GUIDs.Server.Existing.OutOfDate)

    @property
    def AlreadyUpToDate(self):
        return len(self.GUIDs.Server.Existing.UpToDate)

    @property
    def Success(self):
        return self.Status == EvernoteAPIStatus.Success

    @property
    def IsError(self):
        return self.Status.IsError

    @property
    def Status(self):
        s1 = self.Results.Adding.Status
        s2 = self.Results.Updating.Status if self.Results.Updating else EvernoteAPIStatus.Uninitialized
        if s1 == EvernoteAPIStatus.RateLimitError or s2 == EvernoteAPIStatus.RateLimitError:
            return EvernoteAPIStatus.RateLimitError
        if s1 == EvernoteAPIStatus.SocketError or s2 == EvernoteAPIStatus.SocketError:
            return EvernoteAPIStatus.SocketError
        if s1.IsError:
            return s1
        if s2.IsError:
            return s2
        if s1.IsSuccessful and s2.IsSuccessful:
            return EvernoteAPIStatus.Success
        if s2 == EvernoteAPIStatus.Uninitialized:
            return s1
        if s1 == EvernoteAPIStatus.Success:
            return s2
        return s1

    @property
    def SummaryList(self):
        return [
            "New Notes: %d" % self.Adding,
            "Out-Of-Date Notes: %d" % self.Updating,
            "Up-To-Date Notes: %d" % self.AlreadyUpToDate
        ]

    @property
    def Summary(self): return JoinList(self.SummaryList, ' | ', ANKNOTES.FORMATTING.PROGRESS_SUMMARY_PAD)

    def loadAlreadyUpdated(self, db_guids):
        self.GUIDs.Server.Existing.UpToDate = db_guids
        self.GUIDs.Server.Existing.OutOfDate = set(self.GUIDs.Server.Existing.All) - set(
            self.GUIDs.Server.Existing.UpToDate)

    def processUpdateInPlaceResults(self, results):
        return self.processResults(results, EvernoteImportType.UpdateInPlace)

    def processDeleteAndUpdateResults(self, results):
        return self.processResults(results, EvernoteImportType.DeleteAndUpdate)

    @property
    def ResultsSummaryShort(self):
        line = self.Results.Adding.SummaryShort
        if self.Results.Adding.Status.IsError:
            line += " to Anki. Skipping update due to an error (%s)" % self.Results.Adding.Status
        elif not self.Results.Updating:
            line += " to Anki. Updating is disabled"
        else:
            line += " and " + self.Results.Updating.SummaryShort
        return line

    @property
    def ResultsSummaryLines(self):
        lines = [self.ResultsSummaryShort] + self.Results.Adding.SummaryLines
        if self.Results.Updating:
            lines += self.Results.Updating.SummaryLines
        return lines

    @property
    def APICallCount(self):
        return self.Results.Adding.Remote + self.Results.Updating.Remote if self.Results.Updating else 0

    def processResults(self, results, importType=None):
        """
        :type results : EvernoteNoteFetcherResults
        :type importType : EvernoteImportType
        """
        if not importType:
            importType = EvernoteImportType.Add
        results.ImportType = importType
        if importType == EvernoteImportType.Add:
            results.Max = self.Adding
            results.AlreadyUpToDate = 0
            self.Results.Adding = results
        else:
            results.Max = self.Updating
            results.AlreadyUpToDate = self.AlreadyUpToDate
            self.Results.Updating = results

    def __init__(self, anki=None, metadataProgress=None, server_evernote_guids=None, anki_note_ids=None):
        """
        :param anki: Anknotes Main Anki Instance
        :type anki: anknotes.Anki.Anki
        :type metadataProgress: EvernoteMetadataProgress
        :return:
        """
        if not anki:
            return
        self.GUIDs = self._GUIDs(anki, anki_note_ids)
        if metadataProgress:
            server_evernote_guids = metadataProgress.Guids
        if server_evernote_guids:
            self.GUIDs.loadNew(server_evernote_guids)
        self.Results.Adding = EvernoteNoteFetcherResults()
        self.Results.Updating = EvernoteNoteFetcherResults()


class EvernoteMetadataProgress:
    Page = Total = Current = UpdateCount = -1
    Status = EvernoteAPIStatus.Uninitialized
    Guids = []
    NotesMetadata = {}
    """
    :type: dict[str, anknotes.evernote.edam.notestore.ttypes.NoteMetadata]
    """

    @property
    def IsFinished(self):
        return self.Remaining <= 0

    @property
    def SummaryList(self):
        return [["Total Notes: %d" % self.Total,
                 "Total Pages: %d" % self.TotalPages,
                 "Returned Notes: %d" % self.Current,
                 "Result Range: %d-%d" % (self.Offset, self.Completed)
                 ],
                ["Remaining Notes: %d" % self.Remaining,
                 "Remaining Pages: %d" % self.RemainingPages,
                 "Update Count: %d" % self.UpdateCount]]

    @property
    def Summary(self): return JoinList(self.SummaryList, ['\n', ' | '], ANKNOTES.FORMATTING.PROGRESS_SUMMARY_PAD)

    @property
    def QueryLimit(self): return EVERNOTE.IMPORT.QUERY_LIMIT

    @property
    def Offset(self): return (self.Page - 1) * self.QueryLimit

    @property
    def TotalPages(self):
        if self.Total is -1:
            return -1
        p = float(self.Total) / self.QueryLimit
        return int(p) + (1 if p > int(p) else 0)

    @property
    def RemainingPages(self): return max(0, self.TotalPages - self.Page)

    @property
    def Completed(self): return self.Current + self.Offset

    @property
    def Remaining(self): return self.Total - self.Completed

    def __init__(self, page=1):
        self.Page = int(page)

    def loadResults(self, result):
        """
        :param result: Result Returned by Evernote API Call to getNoteMetadata
        :type result: anknotes.evernote.edam.notestore.ttypes.NotesMetadataList
        :return:
        """
        self.Total = int(result.totalNotes)
        self.Current = len(result.notes)
        self.UpdateCount = result.updateCount
        self.Status = EvernoteAPIStatus.Success
        self.Guids = []
        self.NotesMetadata = {}
        for note in result.notes:
            # assert isinstance(note, NoteMetadata)
            self.Guids.append(note.guid)
            self.NotesMetadata[note.guid] = note
