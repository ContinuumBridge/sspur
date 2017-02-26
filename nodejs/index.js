
CB = require('continuumbridge');
logger = CB.logger;

require('./env');

//var args = process.argv.slice(2);
//var key = args[0] || '677182590NDhU2Muu4q+r1kvUwJLvzewv50Wg+26ghkIZwyRYQgOSXEbfSmlB2B8';
logger.log('debug', 'CONTROLLER_SOCKET', CONTROLLER_SOCKET);
var client = new CB.Client({
    key: BRIDGE_KEY,
    cbAPI: CONTROLLER_API,
    cbSocket: CONTROLLER_SOCKET,
    bridge: true
});

var TCPSocket = require('./tcpSocket');

var tcpSocket = new TCPSocket(5000);

tcpSocket.on('message', function(message) {

    // Take messages from the TCP socket and relay them to Continuum Bridge
    client.publish(message);
    logger.log('message', '%s <= %s: '
            ,message.get('destination'), message.get('source'), message.get('body'));
});

client.on('message', function(message) {

    // Take messages from Continuum Bridge and relay them to the TCP socket
    tcpSocket.publish(message);
    logger.log('message', '%s => %s: '
        ,message.get('source'), message.get('destination'), message.get('body'));
});

/*
client.on('connect', function() {
    logger.log('message', 'Bridge connect message');
    var configMessage = new CB.Message({
        'body':
                 {
                      'url': '/api/bridge/v1/current_bridge/bridge',
                      'verb': 'get'
                 },
        'source': 'BID2',
        'destination': 'cb',
        'time_sent': '2014-08-23T01:00:01.238Z'
    });
    var statusMessage = new CB.Message({
        body:
                  {
                       status: 'Bridge state: stopped'
                  },
        source: 'BID2',
        destination: 'broadcast',
        time_sent: '2014-08-23T00:56:41.913Z'
    });
    setTimeout(client.publish(statusMessage), 2000);
});
*/

// Set heartbeat for the local TCP connection
setInterval(function() {

    var message = new CB.Message({
        source: client.cbid
    });
    message.set('body',{connected: client.connected});

    tcpSocket.publish(message);

}, 1000);

