
var Client = require('./client')
    ,TCPSocket = require('./lib/tcpSocket/socket')
    ,Heartbeat = require('./lib/heartbeat')
    ;

var ClientTCP = function(options) {

    var client = new Client(options.key);

    var tcpSocket = new TCPSocket(options.port);

    tcpSocket.on('message', function(message) {

        // Take messages from the client and relay them to the controller
        controllerSocket.toController.push(message);
        logger.info('Client => Controller: ', message);
    });

    // Set heartbeat on the local tcp connection
    setInterval(function() {

        message.set('body',{connected: controllerSocket.connected});
    }, 1000);
    var heartbeat = new Heartbeat(controllerSocket, clientSocket);
    heartbeat.start();
}

module.exports = ClientTCP;