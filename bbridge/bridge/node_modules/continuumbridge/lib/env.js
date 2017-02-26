
var getenv = require('getenv')
    ,path = require('path')
    ,logger = require('./logger')
    ;

// Get some values from the environment
CONTROLLER_API = "http://" + getenv('CB_DJANGO_CONTROLLER_ADDR') + "/api/bridge/v1/";
logger.info('CONTROLLER_API', CONTROLLER_API);

CONTROLLER_SOCKET = "http://" + getenv('CB_NODE_CONTROLLER_ADDR') + "/";
logger.info('CONTROLLER_SOCKET', CONTROLLER_SOCKET);

CLIENT_EMAIL = getenv('CB_BRIDGE_EMAIL', '28b45a59a875478ebcbdf327c18dbfb1@continuumbridge.com');
logger.info('BRIDGE_EMAIL', BRIDGE_EMAIL);

CLIENT_PASSWORD = getenv('CB_BRIDGE_PASSWORD', 'oX3ZGWS/yY1l+PaEFsBp11yixvK6b7O5UiK9M9TV8YBnjPXl3bDLw9eXQZvpmNdr');
logger.info('BRIDGE_PASSWORD', BRIDGE_PASSWORD);

CLIENT_ROOT = path.normalize(__dirname + '/..');
//THIS_BRIDGE_ROOT = path.normalize(__dirname + '/../../thisbridge');
