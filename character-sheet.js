/* exported exports */
var exports = (function() {
    'use strict';
    var SERVER_STORAGE_CGI = 'jsonp_db/',
    throw_error = function () {
        var msg_array = [];
        [].slice.call(arguments).forEach(function (arg) {
            console.log(arg);
            msg_array.push(JSON.stringify(arg));
        });
        var string_message = msg_array.join(' - ');
        alert(string_message);
        throw Error(string_message);
    },
    assert = function (condition, message) {
        if (!condition) {
            message = 'Assert failed' + (typeof message !== 'undefined' ? ': ' + message : '');
            throw_error.bind(null, message, [].slice.call(arguments, 2))();
        }
    },
    encode_query_params = function (data_dict) {
        assert(data_dict, 'Cannot encode empty data dict', data_dict);
        return Object.keys(data_dict).map(function(key) {
            return encodeURIComponent(key) + '=' + encodeURIComponent(data_dict[key]);
        }).join('&');
    },
    get_url_params = function () {
        var urlParams = {};
        window.location.search.substr(1).split('&').forEach(function (item) {
            var pair = item.split('=');
            urlParams[pair[0]] = pair[1];
        });
        return urlParams;
    },
    params = get_url_params(),
    jsonp = (function () {
        var jsonp_calls_counter = 0;
        return function (request) {
            var script = document.createElement('script'),
                callback_func_name = 'jsonp_callback_' + jsonp_calls_counter++,
                callback_param_name = request.callback_param_name || 'callback';
            window[callback_func_name] = function () {
                delete window[callback_func_name];
                request.success.apply(null, arguments);
            };
            script.src = request.url + '?' + callback_param_name + '=' + callback_func_name;
            if (request.params_list) {
                script.src += '&' + request.params_list.map(encodeURIComponent).join('&');
            }
            if (request.params_dict) {
                script.src += '&' + encode_query_params(request.params_dict);
            }
            document.body.appendChild(script);
        };
    })(),
    get_stylesheet = function (css_name) {
        var css_name_pattern = new RegExp(css_name + '$'),
            css_found = null;
        [].slice.call(document.styleSheets).forEach(function (css) {
            if (css.href && css.href.match(css_name_pattern)) {
                css_found = css;
            }
        });
        return css_found;
    },
    get_input_ids_from_css_rules = function (css) {
        var input_ids = {};
        [].slice.call(css.cssRules).forEach(function (rule) {
            var match = rule.selectorText.match(/^(input|textarea)#([^.[]+)(\.([^[]+))?(\[type="(.+)"\])?/);
            if (match) {
                var tag = match[1],
                    id = match[2],
                    className = match[4],
                    input_type = match[6];
                input_ids[id] = {tag: tag, className: className, input_type: input_type};
            }
        });
        return input_ids;
    },
    get_character_id = function (name) {
        return params.layout + '_' + (name || document.getElementById('name').value).replace(/\W+/g, '_').toLowerCase();
    },
    get_location_search = function (name) {
        return '?layout=' + params.layout + '&name=' + (name || document.getElementById('name').value);
    },
    update_title = function (character_id) {
        document.title = 'RPG Character Sheet - ' + character_id;
    },
    fill_inputs = function (inputs_data) {
        [].forEach.call(document.querySelectorAll('#character-sheet input, textarea'), function(input) {
            var value = inputs_data[input.id];
            if (value) {
                if (input.type === 'image') {
                    input.src = value;
                } else if (input.type === 'checkbox') {
                    input.checked = (value === 'on');
                } else {
                    input.value = value;
                }
            }
        });
    },
    scrape_inputs = function () {
        var inputs_data = {};
        [].forEach.call(document.querySelectorAll('#character-sheet input, textarea'), function(input) {
            if (input.type === 'file') {
                return;
            } else if (input.type === 'image') {
                inputs_data[input.id] = input.src;
            } else if (input.type === 'checkbox') {
                inputs_data[input.id] = (input.checked ? 'on' : 'off');
            } else {
                inputs_data[input.id] = input.value;
            }
        });
        return inputs_data;
    },
    exports = {
        save_character_to_server: function () {
            var character_id = get_character_id(),
                modification_key = params['modification-key'];
            assert(character_id, 'No character name provided');
            console.log('Sending character sheet to remote server : ' + character_id);
            var inputs = scrape_inputs();
            jsonp({
                url: SERVER_STORAGE_CGI + character_id,
                params_dict: (modification_key ? {'modification-key': modification_key} : null), // CREATE or UPDATE
                params_list: [JSON.stringify(inputs)],
                success: function (data, new_modification_key) {
                    console.log('Character sheet ' + character_id + ' successfully saved', data);
                    assert(!modification_key || modification_key === new_modification_key,
                            'Modifcation-keys do not match', modification_key, new_modification_key);
                    location.search = get_location_search() + '&modification-key=' + new_modification_key;
                }
            });
        },
        load_character_from_server: function (character_name) {
            var character_id = get_character_id(character_name);
            assert(character_id, 'No character name provided');
            console.log('Fetching character sheet content from server : ' + character_id);
            jsonp({
                url: SERVER_STORAGE_CGI + character_id,
                success: function (data) {
                    if (!data) {
                        console.log('No data found on server matching : ' + character_id);
                        location.search = '?layout=' + params.layout;
                        return;
                    }
                    fill_inputs(data);
                    update_title(character_id);
                }
            });
        },
        download_character_as_json: function () {
            var character_id = get_character_id(),
                data = scrape_inputs(),
                a = document.createElement('a');
            console.log('Downloading JSON file for character: ' + character_id);
            a.href = 'data:application/octet-stream,' + encodeURIComponent(JSON.stringify(data));
            a.download = character_id + '.json';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        },
        charactersheet_file_picker_change: function (files) {
            var reader = new FileReader();
            reader.onload = function() {
                var inputs_data = JSON.parse(reader.result),
                    character_id = get_character_id(inputs_data.name);
                console.log('Uploading character from user-provided file : ' + character_id);
                fill_inputs(inputs_data);
                update_title(character_id);
            };
            reader.readAsText(files[0]);
        },
    };
    document.addEventListener('DOMContentLoaded', function() {
        assert(params.layout, 'No layout specified in the URL');
        var link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = 'css/' + params.layout + '.css';
        document.head.appendChild(link);
        setTimeout(function () { // we wait for the CSS stylesheet to be loaded
            var input_ids = get_input_ids_from_css_rules(get_stylesheet(link.href)),
                main_div = document.getElementById('character-sheet'),
                background_img = document.createElement('img');
            background_img.src = 'img/' + params.layout + '.png';
            background_img.alt = 'Character sheet image cannot be displayed';
            main_div.appendChild(background_img);
            assert(input_ids.name, 'The <layout>.css does not define any #name input, which is required.');
            Object.keys(input_ids).forEach(function (input_id) {
                var input_specs = input_ids[input_id],
                    input = document.createElement(input_specs.tag);
                input.id = input_id;
                if (input_specs.className) {
                    input.className = input_specs.className;
                }
                if (input_specs.tag === 'input') {
                    input.type = input_specs.input_type || 'text';
                }
                if (!params['modification-key'] && input.id !== 'name') {
                    input.readOnly = true;
                }
                main_div.appendChild(input);
                if (input.type === 'image') {
                    input.src = 'icon/upload_image.png';
                    input.onclick = function () {
                        var img_url = prompt('Please enter an URL to the image you want to use', input.src);
                        if (img_url) {
                            input.src = img_url;
                        }
                    };
                }
            });
            if (params.name) {
                exports.load_character_from_server(decodeURIComponent(params.name));
            }
            if (!params['modification-key']) {
                var banner = document.createElement('img');
                banner.src = 'icon/read_only_banner.png';
                banner.id = 'read-only-banner';
                document.body.appendChild(banner);
            }
        }, 1000);
    });
    return exports;
})();
