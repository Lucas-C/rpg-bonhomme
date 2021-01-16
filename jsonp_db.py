#!/usr/bin/env python
import base64, cgi, hashlib, hmac, html, logging, logging.handlers, os, re, sqlite3, traceback
from collections import namedtuple
from threading import Lock
from configobj import ConfigObj
try:
    from urlparse import parse_qsl
except ImportError:
    from urllib.parse import parse_qsl

SCRIPT_DIR = os.path.dirname(__file__) or '.'

CONFIG = ConfigObj(os.path.join(SCRIPT_DIR, re.sub('.pyc?$', '.ini', __file__)))
MAX_KEY_LENGTH = CONFIG.as_int('max_key_length')
MAX_VALUE_LENGTH = CONFIG.as_int('max_value_length')
MAX_TABLE_SIZE = CONFIG.as_int('max_table_size')
REQUIRE_MODIFCATION_KEY = CONFIG.as_bool('require_modification_key')
MODIFICATION_KEY_SALT = CONFIG.get('modification_key_salt').encode('utf8')

LOG_FILE = os.path.join(SCRIPT_DIR, CONFIG.get('log_file'))
LOG_FORMAT = '%(asctime)s - %(process)s [%(levelname)s] %(message)s'

DATABASE_FILE = os.path.join(SCRIPT_DIR, CONFIG.get('db_file'))

HTML_TEMPLATE = """'<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8">
    <title>{title}</title>
  </head>
  <body
{body}
  </body>
</html>"""

HTTP_ERROR_STATUS = {
    400: 'Bad Request',
    401: 'Unauthorized',
    500: 'Internal Server Error'
}
RequestParameters = namedtuple('RequestParameters', 'args kwargs')
class HTTPError(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.code = code
        self.status_string = HTTP_ERROR_STATUS[code]
        self.status_line = '{} {}'.format(code, self.status_string)
        self.full_msg = '{e.status_line} : {e}'.format(e=self)

    def format_response(self, jsonp_callback):
        if jsonp_callback:
            return "{}(new Error('{}'))".format(jsonp_callback, self.full_msg), 'application/javascript'
        html_body = '    <pre>\n' + html.escape(self.full_msg) + '\n    </pre>'
        return HTML_TEMPLATE.format(title=self.status_line, body=html_body), 'text/html'

def application(env, start_response):
    path = env.get('PATH_INFO', '')
    method = env['REQUEST_METHOD']
    query_string = env['QUERY_STRING']
    form = pop_form(env)
    log('Handling request: %s "%s" with query_string: "%s", form: "%s"', method, path, query_string, form)
    # pylint: disable=broad-except
    try:
        try:
            path = path.encode('latin1').decode('utf8')
            query_params = parse_query_string(query_string)
            form_params = parse_form(form)
            callback = query_params.kwargs.pop('callback', None)
            return_values = store_logic(path, query_params, form_params)
            response = ', '.join(return_values)
            if callback:
                response = callback + '(' + response + ')'
            elif len(return_values) > 1:
                response = '[' + response + ']'
            start_response('200 OK', [('Content-Type', 'application/javascript')])
            yield response.encode('utf-8')
        except HTTPError:
            raise
        except Exception as exception:
            raise HTTPError(traceback.format_exc(), code=500) from exception
    except HTTPError as error:
        log(error.full_msg, lvl=logging.ERROR)
        error_response, mime_type = error.format_response(callback)
        start_response(error.status_line, [('Content-Type', mime_type)])
        yield error_response.encode('utf-8')

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
        fp=env.pop('wsgi.input'),
        environ=post_env,
        keep_blank_values=True
    )
    return form

def parse_query_string(query_string):
    qprm = dict(parse_qsl(query_string, True))
    return RequestParameters(
        [k for k in qprm if qprm[k] == ''],
        {k: qprm[k] for k in qprm if qprm[k] != ''},
    )

def parse_form(form):
    return RequestParameters(
        [k for k in form if form[k].value == ''],
        {k: form[k].value for k in form if form[k].value != ''},
    )

def store_logic(path, query_params, form_params):
    if path.startswith('/list_by_prefix/') and path.count('/') == 2:
        return (str(db_list_keys_with_prefix(path[16:])),)  # `str` is used to serialize the array
    key, new_value, modification_key = check_and_extract_params(path, query_params, form_params)
    log('GET key="%s"', key)
    current_value = db_get(key)
    log('-> %s', current_value)
    if not new_value:  # => simple RETRIEVE request
        return (current_value or 'undefined',)
    if REQUIRE_MODIFCATION_KEY:
        if current_value:  # => UPDATE request, we check that the modification-key is valid
            check_modification_key(modification_key, key)
        else:  # => CREATE request, we generate the modification-key
            modification_key = get_modification_key(key)
    # At this point, it's either a CREATE request or a valid UPDATE request
    log('PUT key="%s":value="%s"', key, new_value)
    db_put(key, new_value)
    return new_value, '"{}"'.format(modification_key)

def check_and_extract_params(path, query_params, form_params):
    if not path.startswith('/') or path.count('/') != 1:
        raise HTTPError('Incorrect request syntax, expecting /<key> and got: "{}"'.format(path), code=400)
    key = path[1:]
    if MAX_KEY_LENGTH and (len(key) > MAX_KEY_LENGTH):
        raise ValueError('Key length exceeded maximum: {} > {}'.format(len(key), MAX_KEY_LENGTH))
    modification_key = query_params.kwargs.pop('modification-key', None)
    if query_params.kwargs or form_params.kwargs:
        log('Extra kwargs found: query_params=%s - form_params=%s', query_params.kwargs, form_params.kwargs)
    if len(query_params.args) + len(form_params.args) > 1:
        raise HTTPError(('Incorrect request syntax, extra args:'
                         'query_params={0.args} - form_params={1.args}').format(query_params, form_params), code=400)
    new_value = None
    if form_params.args:
        new_value = form_params.args[0]
    elif query_params.args:
        new_value = query_params.args[0]
    if MAX_VALUE_LENGTH and new_value and len(new_value) > MAX_VALUE_LENGTH:
        raise ValueError('Value length exceeded maximum: {} > {}'.format(len(new_value), MAX_VALUE_LENGTH))
    return key, new_value, modification_key

def check_modification_key(modification_key, key):
    if not modification_key:
        raise HTTPError('No modification-key provided, update forbidden', code=401)
    real_modification_key = get_modification_key(key)
    if real_modification_key != modification_key:
        raise HTTPError('Invalid modification-key, update forbidden: {}'.format(modification_key), code=401)

# To be extra-safe we could use bcrypt instead of MD5 here (or make this a config option), but YAGNI
def get_modification_key(key):
    secret = hmac.new(MODIFICATION_KEY_SALT, key.encode('utf8'), digestmod=hashlib.md5).digest()
    return base64.urlsafe_b64encode(secret).decode('utf8')[:10]

def db_get(key):
    query_result = _DB.execute('SELECT Value FROM KVStore WHERE Key=?', (key,)).fetchone()
    if not query_result or len(query_result) != 1:
        return None
    return query_result[0]

def db_put(key, value):
    db_check_table_size()
    _DB.execute('INSERT OR REPLACE INTO KVStore VALUES (?, ?)', (key, value))

def db_list_keys():
    return [result[0] for result in _DB.execute('SELECT Key FROM KVStore').fetchall()]

def db_list_keys_with_prefix(prefix):
    query = 'SELECT Key FROM KVStore WHERE Key LIKE ? || "%"'
    return [result[0][len(prefix):] for result in _DB.execute(query, (prefix,)).fetchall()]

def db_check_table_size():
    query_result = _DB.execute('SELECT COUNT(*) FROM KVStore').fetchone()
    table_size = int(query_result[0])
    if MAX_TABLE_SIZE and table_size > MAX_TABLE_SIZE:
        raise MemoryError('Table size exceeded limit: {} > {}'.format(table_size, MAX_TABLE_SIZE))

def configure_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    file_handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1024 ** 2, backupCount=10)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(file_handler)
    return logger

def log(msg, *args, lvl=logging.INFO):
    with _LOGGER_LOCK:
        _LOGGER.log(lvl, msg, *args)


_LOGGER = configure_logger()
_LOGGER_LOCK = Lock()
_DB = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
_DB.isolation_level = None  # autocommit mode
if REQUIRE_MODIFCATION_KEY and not MODIFICATION_KEY_SALT:
    raise RuntimeError('A random salt is required when using modification-key based authentication')
log('Starting : %s keys found in the DB - Config: %s', len(db_list_keys()), CONFIG)

if __name__ == '__main__':
    def app(env, start_response):
        path = env.get('PATH_INFO', '').encode('latin1').decode('utf8')
        filename = path[1:] if path else ''
        if filename and os.path.exists(filename):
            filetype = 'text'
            ext = filename.split('.')[-1]
            if ext in ('jpg', 'png'):
                if 'HTTP_IF_NONE_MATCH' in env:  # enabling image caching
                    start_response('304 Not Modified', [])
                    return []
                filetype = 'image'
            start_response('200 OK', [('Content-Type', filetype + '/' + ext), ('Etag', filename)])
            with open(filename, 'rb') as file_obj:
                return [file_obj.read()]
        if env['PATH_INFO'].startswith('/jsonp_db/'):  # match SERVER_STORAGE_CGI in character-sheet.js
            env['PATH_INFO'] = env['PATH_INFO'].replace('/jsonp_db/', '/')
        return application(env, start_response)
    import sys
    PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 80
    from wsgiref.simple_server import make_server
    make_server('localhost', PORT, app).serve_forever()
