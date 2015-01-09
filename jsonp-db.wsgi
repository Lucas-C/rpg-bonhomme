import cgi, json, logging, logging.handlers, os, requests, sqlite3, sys, traceback, urlparse
from contextlib import closing
from functools import wraps
from threading import Lock

MAX_TABLE_SIZE = 1000
MAX_KEY_LENGTH = 100
MAX_VALUE_LENGTH = 10000
DATABASE_FILE = os.path.join(os.path.dirname(__file__), 'jsonp-db.db')
LOG_FILE = os.path.join(os.path.dirname(__file__), 'jsonp-db.log')
LOG_FORMAT = '%(asctime)s - %(process)s [%(levelname)s] %(filename)s %(lineno)d %(message)s'

class Error400(Exception): pass

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
    query_params = dict(urlparse.parse_qsl(env['QUERY_STRING'])) # Note: this discards single values (eg. .../jsonp-db/key?42)
    callback = query_params.pop('callback', None)
    form = pop_form(env)
    log('Handling request: {} "{}" with query_params: "{}", form: "{}"'.format(method, path, query_params, form))
    try:
        response = put_or_get(method, path, query_params, form)
        start_response('200 OK', [('Content-Type', 'application/javascript')])
        return [callback + '(' + response + ')' if callback else response]
    except Error400 as error:
        log('[ERROR] 400 : {}'.format(error))
        error_response, mime_type = format_error_response(error.message, '404 - Client-side error', callback)
        start_response('400 Bad Request', [('Content-Type', mime_type)])
        return [error_response]
    except Exception:
        error_msg = traceback.format_exc()
        log('[ERROR] 500 : {}'.format(error_msg))
        error_response, mime_type = format_error_response(error_msg, '500 - Server-side error', callback)
        start_response('500 Internal Server Error', [('Content-Type', mime_type)])
        return [error_response]

def format_error_response(error_msg, title, callback):
    if callback: # JSONP => call javascript 'alert'
        return ("alert('{}')".format(error_msg), 'application/javascript')
    return (('<!DOCTYPE html><html><head><meta charset="UTF-8"><title>{title}</title></head>'
             '<body><pre>{msg}</pre></body></html>'.format(title=title, msg=cgi.escape(error_msg))), 'text/html')

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
    return {k:form[k].value for k in form.keys()} # Note: this discard single values (eg. curl -d 42 ...)

def put_or_get(method, path, query_params, form):
    if method not in ('GET', 'POST', 'PUT'):
        raise Error400('Invalid method type: {}'.format(method))
    if not path.startswith('/') or path.count('/') != 1:
        raise Error400('Incorrect request syntax, expecting /<key> and got: "{}"'.format(path))
    key = path[1:]
    action = query_params.pop('_do', None)
    try:
        if len(key) > MAX_KEY_LENGTH:
            raise ValueError('Key length exceeded maximum: {} > {}'.format(len(key), MAX_KEY_LENGTH))
        if method == 'GET' and action != 'put':
            log('GET key="{}"'.format(key))
            value = db_get(key)
        else:
            value = query_params if method == 'GET' else form
            log('PUT key="{}":value=""'.format(key, value))
            db_put(key, value)
        return json.dumps({key: value})
    except KeyError:
        return '{}'
    except (ValueError, MemoryError) as error:
        raise Error400('{}: {}'.format(error.__class__.__name__, error.message))


def db_get(key):
    with closing(_db.cursor()) as db_cursor:
        db_cursor.execute('SELECT Value FROM KVStore WHERE Key=?', (key,))
        query_result = db_cursor.fetchone()
    if not query_result or len(query_result) != 1:
        raise KeyError(query_result)
    string_value = query_result[0]
    return json.loads(string_value)

def db_put(key, value):
    db_check_table_size()
    with closing(_db.cursor()) as db_cursor:
        string_value = json.dumps(value)
        if len(string_value) > MAX_VALUE_LENGTH:
            raise ValueError('Value length exceeded maximum: {} > {}'.format(len(string_value), MAX_VALUE_LENGTH))
        db_cursor.execute('INSERT OR REPLACE INTO KVStore VALUES (?, ?)', (key, string_value))
        _db.commit()

def db_check_table_size():
    with closing(_db.cursor()) as db_cursor:
        db_cursor.execute('SELECT COUNT(*) FROM KVStore')
        query_result = db_cursor.fetchone()
    table_size = int(query_result[0])
    if table_size > MAX_TABLE_SIZE:
        raise MemoryError('Table size exceeded limit: {} > {}'.format(table_size, MAX_TABLE_SIZE))
