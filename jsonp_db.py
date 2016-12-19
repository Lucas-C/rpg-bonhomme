import base64, cgi, hashlib, hmac, html, logging, logging.handlers, os, re, requests, sqlite3, traceback
from collections import namedtuple
from contextlib import closing
from threading import Lock
from configobj import ConfigObj
try:
    from urlparse import parse_qsl
except ImportError:
    from urllib.parse import parse_qsl

SCRIPT_DIR = os.path.dirname(__file__) or '.'
CONFIG = ConfigObj(os.path.join(SCRIPT_DIR, re.sub('.pyc?$', '.ini', __file__)))
DATABASE_FILE = os.path.join(SCRIPT_DIR, CONFIG.get('db_file'))
LOG_FILE = os.path.join(SCRIPT_DIR, CONFIG.get('log_file'))
LOG_FORMAT = '%(asctime)s - %(process)s [%(levelname)s] %(message)s'
MAX_KEY_LENGTH = CONFIG.as_int('max_key_length')
MAX_VALUE_LENGTH = CONFIG.as_int('max_value_length')
MAX_TABLE_SIZE = CONFIG.as_int('max_table_size')
REQUIRE_MODIFCATION_KEY = CONFIG.as_bool('require_modification_key')
MODIFICATION_KEY_SALT = CONFIG.get('modification_key_salt').encode('utf8')
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

RequestParameters = namedtuple('RequestParameters', 'args kwargs')
class HTTPError(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.code = code
        self.status_string = error_code_to_status_string(code)
        self.status_line = str(code) + ' ' + self.status_string
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
    log('Handling request: {} "{}" with query_string: "{}", form: "{}"'.format(method, path, query_string, form))
    # pylint: disable=broad-except
    try:
        try:
            query_params = parse_query_string(query_string)
            form_params = parse_form(form)
            callback = query_params.kwargs.pop('callback', None)
            return_values = store_logic(path, query_params, form_params)
            response = callback + '(' + ', '.join(return_values) + ')' if callback else return_values[0]
            start_response('200 OK', [('Content-Type', 'application/javascript')])
            yield response.encode('utf-8')
        except HTTPError:
            raise
        except Exception:
            raise HTTPError(traceback.format_exc(), code=500)
    except HTTPError as error:
        log(error.full_msg, logging.ERROR)
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

def error_code_to_status_string(error_code):
    # pylint: disable=protected-access
    status_strings = requests.status_codes._codes[error_code]
    return ' '.join(w.capitalize() for w in status_strings[0].split('_'))

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
    try:
        key, new_value, modification_key = check_and_extract_params(path, query_params, form_params)
        log('GET key="{}"'.format(key))
        current_value = db_get(key)
        log('-> ' + str(current_value))
        if not new_value:  # => simple RETRIEVE request
            return current_value or 'undefined', 'null'
        elif REQUIRE_MODIFCATION_KEY:
            if current_value:  # => UPDATE request, we check that the modification-key is valid
                check_modification_key(modification_key, key)
            else:  # => CREATE request, we generate the modification-key
                modification_key = get_modification_key(key)
        # At this point, it's either a CREATE request or a valid UPDATE request
        log('PUT key="{}":value="{}"'.format(key, new_value))
        db_put(key, new_value)
        return new_value, '"' + modification_key + '"'
    except Exception:
        raise HTTPError(traceback.format_exc(), code=400)

def check_and_extract_params(path, query_params, form_params):
    if not path.startswith('/') or path.count('/') != 1:
        raise HTTPError('Incorrect request syntax, expecting /<key> and got: "{}"'.format(path), code=400)
    key = path[1:]
    if MAX_KEY_LENGTH and (len(key) > MAX_KEY_LENGTH):
        raise ValueError('Key length exceeded maximum: {} > {}'.format(len(key), MAX_KEY_LENGTH))
    modification_key = query_params.kwargs.pop('modification-key', None)
    if query_params.kwargs or form_params.kwargs:
        log('Extra kwargs found: query_params={0.kwargs} - form_params={1.kwargs}'.format(query_params, form_params))
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
    return base64.urlsafe_b64encode(hmac.new(MODIFICATION_KEY_SALT, key.encode('utf8'), digestmod=hashlib.md5).digest()).decode('utf8')[:10]

def db_get(key):
    with closing(_DB.cursor()) as db_cursor:
        db_cursor.execute('SELECT Value FROM KVStore WHERE Key=?', (key,))
        query_result = db_cursor.fetchone()
    if not query_result or len(query_result) != 1:
        return None
    return str(query_result[0])

def db_put(key, value):
    db_check_table_size()
    with closing(_DB.cursor()) as db_cursor:
        db_cursor.execute('INSERT OR REPLACE INTO KVStore VALUES (?, ?)', (key, value))
        _DB.commit()

def db_list_keys():
    with closing(_DB.cursor()) as db_cursor:
        db_cursor.execute('SELECT Key FROM KVStore')
        return db_cursor.fetchall()

def db_check_table_size():
    with closing(_DB.cursor()) as db_cursor:
        db_cursor.execute('SELECT COUNT(*) FROM KVStore')
        query_result = db_cursor.fetchone()
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

def log(msg, lvl=logging.INFO):
    with _LOGGER_LOCK:
        _LOGGER.log(lvl, msg)

_LOGGER = configure_logger()
_LOGGER_LOCK = Lock()
_DB = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
if REQUIRE_MODIFCATION_KEY and not MODIFICATION_KEY_SALT:
    raise RuntimeError('A random salt is required when using modification-key based authentication')
log('Starting : {} keys found in the DB - Config: {}'.format(len(db_list_keys()), CONFIG))
