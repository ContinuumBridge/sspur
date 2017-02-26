
//var getenv = require('getenv')
var path = require('path')
    ,logger = require('./logger')
    ;

var config = require('../client.json');

CONTROLLER_API = "http://" + config.controller_api + "/api/client/v1/";
logger.info('CONTROLLER_API', CONTROLLER_API);

CONTROLLER_SOCKET = "http://" + config.controller_socket + "/";
logger.info('CONTROLLER_SOCKET', CONTROLLER_SOCKET);

CLIENT_ROOT = path.normalize(__dirname + '/..');
//THIS_CLIENT_ROOT = path.normalize(__dirname + '/../../thisbridge');
