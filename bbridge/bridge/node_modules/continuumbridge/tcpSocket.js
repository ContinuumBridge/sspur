
// Set up the TCP socket for the bridge
var net = require('net')
    ,util = require('util')
    ;

var CB = require('./index');

/* TCP socket manager */

function TCPSocket(port) {

    var self = this;

    this.server = net.createServer(function(socket) {

        socket.setEncoding('utf8');

        self.on('message', function(message) {

            logger.log('debug', 'TCP socket:', message);
            //var jsonMessage = message.getJSON();
        });

        socket.on('data', function(jsonMessage) {

            // There may be multiple messages in each chunk of TCP data.
            var messageArray = JSON.parse('[' + jsonMessage.replace('}{', '},{') + ']');

            _.each(messageArray, function(message) {
                console.log('Received message', message);
                var message = new Message(message);
                self.emit('message', message);
            });
        }); 

        // Add a 'close' event handler for the TCPClient socket
        socket.on('close', function() {

            socket.removeListener('data');
            self.removeListener('message');
            logger.info('TCP socket disconnected');
        }); 

        self.socket = socket;

        logger.info('TCP socket connected');

    }).listen(port);
}

var EventEmitter = require('events').EventEmitter;
util.inherits(TCPSocket, EventEmitter);

TCPSocket.prototype.publish = function(message) {

    var jsonMessage = message instanceof Message ? message.toJSONString() : message;
    if (this.socket) this.socket.write(jsonMessage + '\r\n');
}

module.exports = TCPSocket;

