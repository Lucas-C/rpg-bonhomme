import cgi, logging, logging.handlers, os, sqlite3, traceback, urlparse
from collections import namedtuple
from contextlib import closing
from threading import Lock

MAX_TABLE_SIZE = 1000
MAX_KEY_LENGTH = 100
MAX_VALUE_LENGTH = 10000
DATABASE_FILE = os.path.join(os.path.dirname(__file__), 'jsonp-db.db')
LOG_FILE = os.path.join(os.path.dirname(__file__), 'jsonp-db.log')
LOG_FORMAT = '%(asctime)s - %(process)s [%(levelname)s] %(filename)s %(lineno)d %(message)s'

class Error400(Exception): pass
class RequestParameters(namedtuple('_RequestParameters', 'args kwargs')): pass

def configure_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    file_handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1024*1024, backupCount=10)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(file_handler)
    return logger

_logger = configure_logger()
_logger_lock = Lock()
_db = sqlite3.connect(DATABASE_FILE, check_same_thread=False)

def log(msg, lvl=logging.INFO):
    with _logger_lock:
        _logger.log(lvl, msg)

def application(env, start_response):
    path = env.get('PATH_INFO', '')
    method = env['REQUEST_METHOD']
    query_string = env['QUERY_STRING']
    form = pop_form(env)
    log('Handling request: {} "{}" with query_string: "{}", form: "{}"'.format(method, path, query_string, form))
    try:
        response = handle_request(method, path, query_string, form)
        start_response('200 OK', [('Content-Type', 'application/javascript')])
        return [response]
    except Error400 as error:
        log('[ERROR] 400 : {}'.format(error))
        error_response, mime_type = format_error_response(error.message, '404 - Client-side error', bool(callback))
        start_response('400 Bad Request', [('Content-Type', mime_type)])
        return [error_response]
    except Exception:
        error_msg = traceback.format_exc()
        log('[ERROR] 500 : {}'.format(error_msg))
        error_response, mime_type = format_error_response(error_msg, '500 - Server-side error', bool(callback))
        start_response('500 Internal Server Error', [('Content-Type', mime_type)])
        return [error_response]

def pop_form(env):
    """
    Should be called only ONCE because reading env['wsgi.input'] will empty the stream,
    hence we pop the value
    """
    if 'wsgi.input' not in env:
        return None
    post_env = env.copy()
    post_env['QUERY_STRING'] = ''
    form = cgi.FieldStorage(
        fp = env.pop('wsgi.input'),
        environ = post_env,
        keep_blank_values = True
    )
    return form

def handle_request(method, path, query_string, form):
    query_params = parse_query_string(query_string)
    form_params = parse_form(form)
    callback = query_params.kwargs.pop('callback', None)
    response = put_or_get(path, query_params, form_params)
    return callback + '(' + response + ')' if callback else response

def format_error_response(error_msg, title, use_jsonp):
    if use_jsonp:
        return ("alert('{}')".format(error_msg), 'application/javascript')
    return (('<!DOCTYPE html><html><head><meta charset="UTF-8"><title>{title}</title></head>'
             '<body><pre>{msg}</pre></body></html>'.format(title=title, msg=cgi.escape(error_msg))), 'text/html')

def parse_query_string(query_string):
    qp = dict(urlparse.parse_qsl(query_string, True))
    return RequestParameters(
        [k for k in qp if qp[k] == ''],
        {k:qp[k] for k in qp if qp[k] != ''},
    )

def parse_form(form):
    return RequestParameters(
        [k for k in form if form[k].value == ''],
        {k:form[k].value for k in form if form[k].value != ''},
    )

def put_or_get(path, query_params, form_params):
    if not path.startswith('/') or path.count('/') != 1:
        raise Error400('Incorrect request syntax, expecting /<key> and got: "{}"'.format(path))
    if len(query_params.args) > 1 or len(form_params.args) > 1:
        raise Error404(('Incorrect request syntax, extra args:'
                + 'query_params={.args} - form_params={.args}').format(query_params, form_params))
    if query_params.kwargs or form_params.kwargs:
        log(('Extra kwargs found:'
            + 'query_params={.kwargs} - form_params={.kwargs}').format(query_params, form_params))
    key = path[1:]
    value = None
    if form_params.args:
        value = form_params.args[0]
    elif query_params.args:
        value = query_params.args[0]
    try:
        return db_put_or_get(key, value)
    except KeyError:
        return 'undefined'
    except (ValueError, MemoryError) as error:
        raise Error400('{}: {}'.format(error.__class__.__name__, error.message))

def db_put_or_get(key, value):
    if len(key) > MAX_KEY_LENGTH:
        raise ValueError('Key length exceeded maximum: {} > {}'.format(len(key), MAX_KEY_LENGTH))
    if value:
        if len(value) > MAX_VALUE_LENGTH:
            raise ValueError('Value length exceeded maximum: {} > {}'.format(len(value), MAX_VALUE_LENGTH))
        log('PUT key="{}":value="{}"'.format(key, value))
        db_put(key, value)
    else:
        log('GET key="{}"'.format(key))
        value = db_get(key)
    return value

def db_get(key):
    with closing(_db.cursor()) as db_cursor:
        db_cursor.execute('SELECT Value FROM KVStore WHERE Key=?', (key,))
        query_result = db_cursor.fetchone()
    if not query_result or len(query_result) != 1:
        raise KeyError(query_result)
    return str(query_result[0])

def db_put(key, value):
    db_check_table_size()
    with closing(_db.cursor()) as db_cursor:
        db_cursor.execute('INSERT OR REPLACE INTO KVStore VALUES (?, ?)', (key, value))
        _db.commit()

def db_check_table_size():
    with closing(_db.cursor()) as db_cursor:
        db_cursor.execute('SELECT COUNT(*) FROM KVStore')
        query_result = db_cursor.fetchone()
    table_size = int(query_result[0])
    if table_size > MAX_TABLE_SIZE:
        raise MemoryError('Table size exceeded limit: {} > {}'.format(table_size, MAX_TABLE_SIZE))
