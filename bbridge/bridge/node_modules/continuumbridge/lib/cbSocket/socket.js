
var io = require('socket.io-client')
    ,util = require('util');

var logger = require('../logger')
    ,Message = require('../message')
    ;

/* CB socket manager */

function CBSocketWrapper(config) {

    this.config = config;

    var self = this;

    // Connection status flag
    this.connected = false;

    // Socket Wrapper listeners
    this.on('connect', function() {
        self.connected = true;
        logger.info('Connected to Continuum Bridge', self.config.cbSocket);
    });
    this.on('connecting', function() {
        self.connected = false;
        logger.info('Connecting..');
    });
    this.on('error', function(error) {
        self.connected = false;
        logger.log('Error', error);
    });
    this.on('disconnect', function() {
        self.connected = false;
        logger.info('Disconnected from Continuum Bridge:', self.config.cbSocket);
    });
}

var EventEmitter = require('events').EventEmitter;
util.inherits(CBSocketWrapper, EventEmitter);

CBSocketWrapper.prototype.connect = function(sessionID) {

    var self = this;

    var socketAddress = this.config.cbSocket + "?sessionID=" + sessionID;
    var socket = this.socket = io.connect(socketAddress);

    // Proxy socket events to the controllerSocketWrapper
    // Connected
    socket.on('connect', function() {
        logger.log('debug', 'socket connect', self.config.cbSocket);
        self.emit('connect');
    });
    socket.on('reconnect', function() {
        logger.log('debug', 'socket reconnect', self.config.cbSocket);
    });

    // Messages
    socket.on('message', function(jsonMessage) {
        var message = new Message(jsonMessage);
        self.emit('message', message);
    });

    // Connecting
    socket.on('reconnecting', function() {
        logger.log('debug', 'socket connecting', self.config.cbSocket);
        self.emit('connecting');
    });

    // Timeout
    socket.on('connect_timeout', function() {
        logger.log('debug', 'connect timeout', self.config.cbSocket);
        self.emit('timeout');
        self.emit('disconnect');
    });
    // Error
    socket.on('connect_error', function(error) {
        logger.log('debug', 'connect error', self.config.cbSocket);
        self.emit('error', error);
        self.emit('disconnect');
    });

    // Failed
    socket.on('reconnect_failed', function() {
        logger.log('debug', 'socket disconnect', self.config.cbSocket);
        self.emit('disconnect');
        self.emit('fail');
    });

    logger.info('Establishing socket to Controller:', self.config.cbSocket);
};

CBSocketWrapper.prototype.giveUp = function() {

    logger.log('debug', 'giveUp');
    if (this.socket) {
        var socket = this.socket;
        socket.removeAllListeners();
        socket.disconnect();
        delete socket;
    }
};

module.exports = CBSocketWrapper;

