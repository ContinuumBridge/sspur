
CB = require('./index');
logger = CB.logger;

var client = new CB.Client({
    key: '677182590NDhU2Muu4q+r1kvUwJLvzewv50Wg+26ghkIZwyRYQgOSXEbfSmlB2B8'
});

var TCPSocket = require('./tcpSocket');

var tcpSocket = new TCPSocket(5000);

tcpSocket.on('message', function(message) {

    // Take messages from the TCP socket and relay them to Continuum Bridge
    client.publish(message);
    logger.log('message', '%s <= %s: %s'
            ,message.get('destination'), message.get('source'), message.get('body'));
});

client.on('message', function(message) {

    // Take messages from Continuum Bridge and relay them to the TCP socket
    tcpSocket.publish(message);
    logger.log('message', '%s => %s: %s'
        ,message.get('source'), message.get('destination'), message.get('body'));
});

// Set heartbeat for the local TCP connection
setInterval(function() {

    var message = new CB.Message({
        source: client.cbid
    });
    message.set('body',{connected: client.connected});

    tcpSocket.publish(message);

}, 1000);
