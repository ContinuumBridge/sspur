
var getenv = require('getenv');

// Get some values from the environment
CONTROLLER_API = "http://" + getenv('CB_DJANGO_CONTROLLER_ADDR', '54.72.38.223') + "/api/bridge/v1/";
//CONTROLLER_API = "http://" + getenv('CB_DJANGO_CONTROLLER_ADDR', '54.194.73.211:8000') + "/api/bridge/v1/";
logger.info('CONTROLLER_API', CONTROLLER_API);

CONTROLLER_SOCKET = "http://" + getenv('CB_NODE_CONTROLLER_ADDR', '54.72.38.223');
logger.info('CONTROLLER_SOCKET', CONTROLLER_SOCKET);

// Dev
//BRIDGE_KEY = getenv('CB_BRIDGE_KEY', '930f0f10BOd/FfDpoYEilLJN+eZTvWTUseRgGpDw8WmzKGHsPo/97Y1jM2Dz9vfE');
// Staging
BRIDGE_KEY = getenv('CB_BRIDGE_KEY', '6005ce85NmQl2ruiJ6Zd0MZvpQK3mdclgpP3DMuu63ZkJAeND8SzFuXVnO2s23Ey');
logger.info('BRIDGE_KEY', BRIDGE_KEY);